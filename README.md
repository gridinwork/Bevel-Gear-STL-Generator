# Bevel Gear STL Generator

![Bevel Gear STL Generator interface](IMG/interface.png)

A desktop parametric bevel-gear generator with interactive 3D preview and STL export. The application is designed for quickly creating customizable bevel gear models for prototyping, CAD work, mechanical experiments, and 3D printing.

## Project Overview

This project focuses specifically on **bevel gears**, where the tooth geometry is distributed around a tapered gear body rather than a cylindrical spur-gear body. It is a separate application from the modular spur/helical gear generator because the geometry, controls, and model-building workflow are different.

The program provides a graphical interface for defining the principal gear dimensions, generating the model, inspecting it in an embedded 3D viewer, and exporting the resulting mesh as an STL file.

## Main Features

- Parametric bevel-gear generation
- Configurable tooth count
- Adjustable outer diameter
- Adjustable gear height / thickness
- Pressure-angle configuration
- Configurable center bore
- Keyway-related dimensions
- Mesh/detail resolution control
- Interactive 3D preview
- Dimension and geometry visualization
- STL export
- Dark desktop interface
- Windows-oriented workflow
- Standalone executable build support

## Parametric Controls

The application exposes the main parameters required to rapidly create and compare bevel-gear variants. Depending on the selected configuration, parameters include the number of teeth, outside diameter, overall height, bore diameter, keyway dimensions, pressure angle, and model resolution.

## 3D Preview

The integrated 3D viewer is based on PyVista/VTK and provides immediate visual feedback before export. The user can rotate and inspect the generated gear and evaluate the tooth shape, bore, proportions, and overall form before creating the STL file.

## STL Export

The final geometry can be exported directly as STL for use with FDM or resin 3D printers, slicer software, CAD assemblies, mechanical prototypes, educational models, robotics, and transmission experiments.

## Technology Stack

- Python
- PySide6 / Qt desktop interface
- PyVista
- VTK
- NumPy
- Trimesh and related mesh-processing tools where used by the project
- PyInstaller for optional standalone Windows builds

## Typical Workflow

1. Enter the required number of teeth.
2. Define the main gear dimensions.
3. Configure the center bore and keyway options.
4. Set the pressure angle and model resolution.
5. Generate or refresh the 3D preview.
6. Inspect the model from different angles.
7. Export the finished gear as STL.

## Use Cases

- Custom bevel-gear prototypes
- 3D-printed transmissions
- Robotics mechanisms
- Educational demonstrations
- Rapid mechanical design experiments
- CAD concept development

## Future Development

Possible future improvements include additional bevel-gear geometry options, mating-pair generation, more advanced tooth calculations, tolerance/backlash controls, additional export formats, and expanded manufacturing presets.

## Disclaimer

The generated models are intended for prototyping and engineering development. For load-bearing or safety-critical applications, gear geometry, materials, clearances, manufacturing tolerances, lubrication, and applicable mechanical standards should be independently verified.
