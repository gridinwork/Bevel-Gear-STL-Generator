import sys
import os
import math
import subprocess
import threading
import shutil
from pathlib import Path

import numpy as np
import trimesh

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QDoubleSpinBox, QSpinBox,
    QPushButton, QGridLayout, QVBoxLayout, QHBoxLayout, QFileDialog, QTextEdit,
    QGroupBox, QMessageBox, QSplitter, QCheckBox
)
from PySide6.QtCore import Qt, Signal, QObject

import pyvista as pv
from pyvistaqt import QtInteractor


APP_NAME = "BevelGearGenerator"


def app_base_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


class BuildSignals(QObject):
    log = Signal(str)
    done = Signal(bool, str)


def build_gear(teeth=22, height=10.0, outer_d=34.0, cut_start_d=20.0, flat_d=16.0,
               bore_d=8.0, key_w=2.8, key_depth=1.5, pressure_angle=20.0,
               segments_per_tooth=12, levels=32):
    n = int(teeth) * int(segments_per_tooth)
    verts, faces = [], []

    def add_ring(z, radii):
        s = len(verts)
        for i, r in enumerate(radii):
            a = 2 * math.pi * i / n
            verts.append([r * math.cos(a), r * math.sin(a), z])
        return s

    def tooth_wave(i):
        p = (i % segments_per_tooth) / segments_per_tooth
        tri = 1.0 - abs(p - 0.5) * 2.0
        sharpness = max(0.35, min(0.95, 0.75 - (pressure_angle - 20.0) * 0.008))
        return max(0.0, tri) ** sharpness

    outer_r = outer_d / 2
    cut_r = cut_start_d / 2
    bore_r = bore_d / 2
    key_r = bore_r + key_depth

    def inner_radius(angle):
        if key_w <= 0 or key_depth <= 0:
            return bore_r
        a = (angle + 2 * math.pi) % (2 * math.pi)
        window = math.atan((key_w / 2) / max(key_r, 0.01))
        return key_r if abs(a - math.pi / 2) <= window else bore_r

    rings = []
    for k in range(levels + 1):
        t = k / levels
        z = -height / 2 + t * height
        mid = 1.0 - abs(t - 0.5) * 2.0

        root_center_r = cut_r + (outer_r - cut_r) * 0.52
        root_r = cut_r * (1 - mid) + root_center_r * mid
        tip_r = cut_r * (1 - mid) + outer_r * mid

        radii = [root_r + (tip_r - root_r) * tooth_wave(i) for i in range(n)]
        rings.append(add_ring(z, radii))

    for k in range(levels):
        r0, r1 = rings[k], rings[k + 1]
        for i in range(n):
            j = (i + 1) % n
            faces.append([r0 + i, r0 + j, r1 + j])
            faces.append([r0 + i, r1 + j, r1 + i])

    inner_radii = [inner_radius(2 * math.pi * i / n) for i in range(n)]
    inner_bottom = add_ring(-height / 2, inner_radii)
    inner_top = add_ring(height / 2, inner_radii)

    bottom_outer, top_outer = rings[0], rings[-1]

    for i in range(n):
        j = (i + 1) % n
        faces.append([top_outer + i, top_outer + j, inner_top + j])
        faces.append([top_outer + i, inner_top + j, inner_top + i])

        faces.append([bottom_outer + j, bottom_outer + i, inner_bottom + i])
        faces.append([bottom_outer + j, inner_bottom + i, inner_bottom + j])

        faces.append([inner_bottom + i, inner_bottom + j, inner_top + j])
        faces.append([inner_bottom + i, inner_top + j, inner_top + i])

    return trimesh.Trimesh(vertices=np.array(verts), faces=np.array(faces), process=True)


def trimesh_to_pyvista(mesh: trimesh.Trimesh) -> pv.PolyData:
    faces = np.hstack([np.full((len(mesh.faces), 1), 3), mesh.faces]).astype(np.int64)
    return pv.PolyData(mesh.vertices, faces)


def polyline(points):
    points = np.asarray(points, dtype=float)
    cells = np.full((1, len(points) + 1), len(points), dtype=np.int64)
    cells[0, 1:] = np.arange(len(points))
    return pv.PolyData(points, lines=cells)


def circle_polyline(radius, z, count=180):
    pts = []
    for i in range(count + 1):
        a = 2 * math.pi * i / count
        pts.append([radius * math.cos(a), radius * math.sin(a), z])
    return polyline(pts)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Bevel Gear Generator v6 — EXE Builder")
        self.resize(1520, 880)
        self.current_mesh = None
        self.build_signals = BuildSignals()
        self.build_signals.log.connect(self.log_append)
        self.build_signals.done.connect(self.on_build_done)

        root = QWidget()
        self.setCentralWidget(root)
        main_layout = QVBoxLayout(root)

        title = QLabel("Генератор конической шестерни STL — OpenGL + сборка EXE")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 24px; font-weight: bold; padding: 8px;")
        main_layout.addWidget(title)

        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)

        left = QWidget()
        left_layout = QVBoxLayout(left)

        grid_box = QGroupBox("Параметры модели, мм")
        grid = QGridLayout(grid_box)

        self.teeth = self.spin_int(22, 6, 120)
        self.height = self.spin(10.0, 1, 80)
        self.outer_d = self.spin(34.0, 5, 300)
        self.cut_start_d = self.spin(20.0, 1, 290)
        self.flat_d = self.spin(16.0, 1, 280)
        self.bore_d = self.spin(8.0, 0.5, 200)
        self.key_w = self.spin(2.8, 0, 50)
        self.key_depth = self.spin(1.5, 0, 50)
        self.pressure_angle = self.spin(20.0, 10, 35)
        self.segments = self.spin_int(12, 6, 28)
        self.levels = self.spin_int(32, 12, 70)

        self.checks = {}
        rows = [
            ("Количество зубьев", self.teeth, "teeth"),
            ("Толщина / высота", self.height, "height"),
            ("Наружный диаметр по зубьям", self.outer_d, "outer_d"),
            ("Диаметр начала среза", self.cut_start_d, "cut_start_d"),
            ("Центральная плоская зона", self.flat_d, "flat_d"),
            ("Внутреннее отверстие", self.bore_d, "bore_d"),
            ("Шпоночный паз — ширина", self.key_w, "keyway"),
            ("Шпоночный паз — глубина от круга", self.key_depth, "keyway"),
            ("Угол давления, °", self.pressure_angle, None),
            ("Сегментов на зуб", self.segments, None),
            ("Слоёв по высоте", self.levels, None),
        ]

        for r, (name, widget, key) in enumerate(rows):
            grid.addWidget(QLabel(name), r, 0)
            grid.addWidget(widget, r, 1)
            if key and key not in self.checks:
                cb = QCheckBox("показать")
                cb.stateChanged.connect(self.redraw_dimensions)
                self.checks[key] = cb
                grid.addWidget(cb, r, 2)
            else:
                grid.addWidget(QLabel(""), r, 2)

        left_layout.addWidget(grid_box)

        btns = QHBoxLayout()
        self.btn_preview = QPushButton("Обновить предпросмотр")
        self.btn_preview.clicked.connect(self.update_preview)
        self.btn_export = QPushButton("Сохранить STL")
        self.btn_export.clicked.connect(self.export_stl)
        btns.addWidget(self.btn_preview)
        btns.addWidget(self.btn_export)
        left_layout.addLayout(btns)

        btns2 = QHBoxLayout()
        self.btn_fit = QPushButton("Вписать модель")
        self.btn_fit.clicked.connect(self.reset_camera)
        self.btn_preset = QPushButton("Параметры как на чертеже")
        self.btn_preset.clicked.connect(self.set_preset)
        btns2.addWidget(self.btn_fit)
        btns2.addWidget(self.btn_preset)
        left_layout.addLayout(btns2)

        self.btn_build_exe = QPushButton("Собрать EXE для Windows")
        self.btn_build_exe.clicked.connect(self.build_exe_gui)
        self.btn_build_exe.setStyleSheet("background: #16a34a; color: white; padding: 12px; font-weight: bold;")
        left_layout.addWidget(self.btn_build_exe)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setText(
            "v6: добавлена кнопка сборки EXE.\n"
            "EXE собирается через PyInstaller в папку dist\\BevelGearGenerator.\n"
            "После сборки можно перенести всю папку dist\\BevelGearGenerator на другой Windows-компьютер.\n"
        )
        left_layout.addWidget(self.log)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        self.plotter = QtInteractor(right)
        right_layout.addWidget(self.plotter.interactor)

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setSizes([500, 1020])

        self.set_dark_theme()
        self.update_preview()

    def setup_scene(self):
        self.plotter.set_background("#d8d8d8")
        self.plotter.enable_anti_aliasing()
        self.plotter.add_axes()
        self.plotter.show_grid(color="#b5b5b5")
        try:
            self.plotter.enable_eye_dome_lighting()
        except Exception:
            pass
        self.plotter.add_light(pv.Light(position=(60, -50, 60), focal_point=(0, 0, 0), color="white", intensity=0.9))
        self.plotter.add_light(pv.Light(position=(-40, 30, 50), focal_point=(0, 0, 0), color="white", intensity=0.35))

    def spin(self, value, mn, mx):
        s = QDoubleSpinBox()
        s.setDecimals(3)
        s.setRange(mn, mx)
        s.setSingleStep(0.1)
        s.setValue(value)
        return s

    def spin_int(self, value, mn, mx):
        s = QSpinBox()
        s.setRange(mn, mx)
        s.setValue(value)
        return s

    def values(self):
        return dict(
            teeth=self.teeth.value(), height=self.height.value(), outer_d=self.outer_d.value(),
            cut_start_d=self.cut_start_d.value(), flat_d=self.flat_d.value(), bore_d=self.bore_d.value(),
            key_w=self.key_w.value(), key_depth=self.key_depth.value(), pressure_angle=self.pressure_angle.value(),
            segments_per_tooth=self.segments.value(), levels=self.levels.value()
        )

    def update_preview(self):
        try:
            self.log_append("\nСоздаю модель...")
            self.current_mesh = build_gear(**self.values())
            pv_mesh = trimesh_to_pyvista(self.current_mesh)

            self.plotter.clear()
            self.setup_scene()

            self.plotter.add_mesh(
                pv_mesh,
                color="#8b8b8b",
                smooth_shading=False,
                show_edges=False,
                specular=0.55,
                specular_power=45,
                ambient=0.22,
                diffuse=0.82,
                split_sharp_edges=True,
            )

            try:
                feature_edges = pv_mesh.extract_feature_edges(
                    boundary_edges=False, non_manifold_edges=False,
                    feature_edges=True, manifold_edges=False, feature_angle=35
                )
                self.plotter.add_mesh(feature_edges, color="#3f3f3f", line_width=1.2)
            except Exception:
                pass

            self.add_dimensions()
            self.plotter.camera_position = "iso"
            self.plotter.reset_camera()
            self.plotter.render()
            self.log_append(f"Готово. Треугольников: {len(self.current_mesh.faces)}")
        except Exception as e:
            self.log_append(f"ОШИБКА: {e}")
            QMessageBox.critical(self, "Ошибка", str(e))

    def redraw_dimensions(self):
        if self.current_mesh is not None:
            self.update_preview()

    def add_label(self, point, text, size=18):
        self.plotter.add_point_labels(
            [point], [text], font_size=size, text_color="black", point_size=0,
            shape_color="white", shape_opacity=0.55, always_visible=True
        )

    def add_segment(self, a, b, text):
        self.plotter.add_mesh(polyline([a, b]), color="black", line_width=3)
        mid = ((np.array(a) + np.array(b)) / 2).tolist()
        self.add_label(mid, text, 18)

    def add_dimensions(self):
        p = self.values()
        r = p["outer_d"] / 2
        h = p["height"]

        if self.checks.get("outer_d") and self.checks["outer_d"].isChecked():
            self.add_segment([-r, -r-5, 0], [r, -r-5, 0], f"Ø{p['outer_d']:.2f} мм")
        if self.checks.get("height") and self.checks["height"].isChecked():
            self.add_segment([r+5, 0, -h/2], [r+5, 0, h/2], f"{h:.2f} мм")
        if self.checks.get("teeth") and self.checks["teeth"].isChecked():
            self.add_label([-r, r+5, h/2 + 2], f"Зубьев: {int(p['teeth'])}", 18)
            pts = [[r*math.cos(2*math.pi*i/int(p["teeth"])), r*math.sin(2*math.pi*i/int(p["teeth"])), 0] for i in range(int(p["teeth"]))]
            self.plotter.add_points(np.array(pts), color="black", point_size=8)

        for key, dia, label, offset in [
            ("cut_start_d", p["cut_start_d"], "начало среза", 1.3),
            ("flat_d", p["flat_d"], "плоская зона", 2.1),
            ("bore_d", p["bore_d"], "отверстие", 2.9),
        ]:
            if self.checks.get(key) and self.checks[key].isChecked():
                rr = dia / 2
                self.plotter.add_mesh(circle_polyline(rr, h/2 + offset), color="black", line_width=2)
                self.add_label([rr, 0, h/2 + offset + 0.6], f"Ø{dia:.2f} {label}", 16)

        if self.checks.get("keyway") and self.checks["keyway"].isChecked():
            self.add_label([0, p["bore_d"]/2 + p["key_depth"] + 3, h/2 + 3.2],
                           f"паз {p['key_w']:.2f}×{p['key_depth']:.2f} мм", 16)

    def reset_camera(self):
        self.plotter.reset_camera()
        self.plotter.render()

    def export_stl(self):
        try:
            path, _ = QFileDialog.getSaveFileName(
                self, "Сохранить STL", "gear_22t_OD34_cut20_H10_bore8_keyway.stl", "STL files (*.stl)"
            )
            if not path:
                return
            if not path.lower().endswith(".stl"):
                path += ".stl"
            mesh = build_gear(**self.values())
            mesh.export(path)
            self.log_append(f"\nSTL сохранён: {path}")
            QMessageBox.information(self, "Готово", f"STL сохранён:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", str(e))

    def set_preset(self):
        self.teeth.setValue(22)
        self.height.setValue(10.0)
        self.outer_d.setValue(34.0)
        self.cut_start_d.setValue(20.0)
        self.flat_d.setValue(16.0)
        self.bore_d.setValue(8.0)
        self.key_w.setValue(2.8)
        self.key_depth.setValue(1.5)
        self.pressure_angle.setValue(20.0)
        self.segments.setValue(12)
        self.levels.setValue(32)
        self.update_preview()

    def build_exe_gui(self):
        if getattr(sys, "frozen", False):
            QMessageBox.warning(
                self, "Сборка EXE",
                "Сборку EXE нужно запускать из исходной папки программы, а не из уже собранного EXE."
            )
            return

        answer = QMessageBox.question(
            self, "Собрать EXE",
            "Сборка может занять 5–20 минут и скачать PyInstaller, если он не установлен.\n\n"
            "После сборки готовая программа будет в папке:\n"
            "dist\\BevelGearGenerator\\BevelGearGenerator.exe\n\n"
            "Начать сборку?",
            QMessageBox.Yes | QMessageBox.No
        )
        if answer != QMessageBox.Yes:
            return

        self.btn_build_exe.setEnabled(False)
        self.log_append("\n=== Запуск сборки EXE ===")

        thread = threading.Thread(target=self.build_exe_worker, daemon=True)
        thread.start()

    def build_exe_worker(self):
        try:
            project_dir = app_base_dir()
            python_exe = sys.executable
            self.build_signals.log.emit(f"Папка проекта: {project_dir}")
            self.build_signals.log.emit(f"Python: {python_exe}")

            self.build_signals.log.emit("Проверяю/устанавливаю PyInstaller...")
            subprocess.check_call([python_exe, "-m", "pip", "install", "--upgrade", "pyinstaller"],
                                  cwd=project_dir)

            for name in ["build", "dist"]:
                p = project_dir / name
                if p.exists():
                    self.build_signals.log.emit(f"Удаляю старую папку: {p}")
                    shutil.rmtree(p, ignore_errors=True)

            spec = project_dir / "BevelGearGenerator.spec"
            if spec.exists():
                spec.unlink()

            cmd = [
                python_exe, "-m", "PyInstaller",
                "--noconfirm",
                "--clean",
                "--windowed",
                "--name", APP_NAME,
                "--collect-all", "pyvista",
                "--collect-all", "pyvistaqt",
                "--collect-all", "vtk",
                "--collect-all", "trimesh",
                "--collect-all", "numpy",
                "main.py"
            ]

            self.build_signals.log.emit("Команда сборки:")
            self.build_signals.log.emit(" ".join(cmd))

            proc = subprocess.Popen(
                cmd,
                cwd=project_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace"
            )

            for line in proc.stdout:
                self.build_signals.log.emit(line.rstrip())

            code = proc.wait()
            if code != 0:
                raise RuntimeError(f"PyInstaller завершился с кодом ошибки: {code}")

            exe_path = project_dir / "dist" / APP_NAME / f"{APP_NAME}.exe"
            if not exe_path.exists():
                raise RuntimeError(f"EXE не найден после сборки: {exe_path}")

            self.build_signals.done.emit(True, str(exe_path))
        except Exception as e:
            self.build_signals.done.emit(False, str(e))

    def on_build_done(self, ok, message):
        self.btn_build_exe.setEnabled(True)
        if ok:
            self.log_append("\n=== EXE успешно собран ===")
            self.log_append(message)
            QMessageBox.information(self, "EXE готов", f"EXE собран:\n{message}\n\nПереноси всю папку dist\\BevelGearGenerator.")
        else:
            self.log_append("\n=== ОШИБКА СБОРКИ EXE ===")
            self.log_append(message)
            QMessageBox.critical(self, "Ошибка сборки EXE", message)

    def log_append(self, text):
        self.log.append(text)
        self.log.verticalScrollBar().setValue(self.log.verticalScrollBar().maximum())

    def set_dark_theme(self):
        self.setStyleSheet("""
            QMainWindow, QWidget { background: #202124; color: #eeeeee; }
            QGroupBox { border: 1px solid #555; border-radius: 8px; margin-top: 10px; padding: 10px; }
            QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; }
            QLabel { font-size: 14px; }
            QCheckBox { font-size: 12px; }
            QPushButton { background: #2d7dff; color: white; padding: 10px; border-radius: 6px; font-weight: bold; }
            QPushButton:hover { background: #4c91ff; }
            QSpinBox, QDoubleSpinBox, QTextEdit { background: #2b2c30; color: #ffffff; border: 1px solid #666; padding: 4px; }
            QSplitter::handle { background: #333; }
        """)


def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
