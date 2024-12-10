# Simple CPP Hot Reloader

Simple CPP Hot Reloader or in shorter terms "schr", is a configuration less, stateless hot reloader for c and cpp projects.

To use schr, you don't need to modify the source code of your application, you only need to tell schr what it needs to build your project.

## Installation

WIP:
* I am working on a script to install schr from source
* I am also looking for a way to install schr through pip
* And I am also looking for a way to install a binary build of schr with [nuitka](https://nuitka.net/)

## Usage

WIP: this section will be updated as soon as I have finished the installation guide of schr (ie being able to run it with the `schr` command)

To use schr with your project, run the following command :

```bash
python cli.py -t <path/to/your/project/built/executable>
```

This command is the bare minimum for schr to start, maybe it will work, maybe not.

To make sure that schr will be able to build your project, you must pass your project metadata (ie compiler, compiler flags, stdlib version, ...) as argument in the command.

Here are the arguments that can be used to inform schr

| Argument | Usage | Description | Default |
| --- | --- | --- | --- |
| -c,--compiler | -c COMPILER | C/C++ compiler executable | g++ |
| -cf,--cflags | -cf="..." | C/C++ compiler flags | |
| -ld,--ldflags | -ld="..." | C/C++ compiler linker flags | |
| -od,--obj-dir | -od OBJ_DIR | Object files output directory | By default, object files are outputed next to the source code |
| -t,--target | -t TARGET | The path to your project built executable | |
| -ta,--target-args | -ta="..." | Arguments to pass to your project built executable when restarted by schr | |
| -m,--mode | -m MODE |  A combination of characters describing the hot reloader behaviour (see [Modes](#modes)) | CR |
| -d,--debug | -d | Enable debug mode, compiler commands will be printed | Disabled |
| --makefile | --makefile | Print the source code of a makefile that can be used to execute schr with the provided arguments | Disabled |

Thus, if you need to compile your project with clang, you can use the **-c** flag :

```bash
python cli.py -t <path/to/your/project/built/executable> -c clang
```

If you need to use c++20 and add a `src` directory to the include path, you can use the **-cf** flag :

```bash
python cli.py -t <path/to/your/project/built/executable> -cf="-std=c++20 -I./src"
```

If you want to output every object file (*.o) to a `bin` folder, you can use the **-od** flag :

```bash
python cli.py -t <path/to/your/project/built/executable> -od ./bin
```

For other examples see [Examples](#examples)


## [Modes](#modes)

When running schr, you may only want to recompile your project and run it when your are finished working, or you may want to restart your project when a change occurs.

The mode flag **-m**,**--mode** is a combinaison of the following values : C, R.

* C correspond to the "Compilation" mode. When enabled, any change to a source file will be instantly recompiled.
* R correspond to the "Restart" mode. When enabled, your project built binary will be restarted everytime your project is linked (ie the compilation is done)

You can use both mode a the same time (eg `-m CR`) or only a given one (eg `-m C`).

By default, C and R mode are enabled.

## Examples

WIP

## Improvements 

* Slow start: I tested schr on a cpp vulkan project with over 60+ files, schr needed at least 20-30 seconds to boot. Even though I am coding on a potato, the initial dependency graph computation could be sped up using multithreading.
* Proper testing: schr is considered stable because it works on my machine. Ideally, I will write unit tests to confirm my thought.