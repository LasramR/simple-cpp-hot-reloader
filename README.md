# Simple CPP Hot Reloader

Simple CPP Hot Reloader or in shorter terms "schr", is a configurationless, stateless hot reloader for C and CPP projects.

To use schr, you don't need to modify the source code of your application, you only need to tell schr what it needs to build your project.

**schr only works on Unix systems (ie not Windows).**

## Installation

### Single command

You can install schr by running the following command :

```sh
git clone https://github.com/LasramR/simple-cpp-hot-reloader.git ~/.schr && chmod +x ~/.schr/_install.sh && ~/.schr/_install.sh
```

### Do it yourself

You may notice that the single command installation of schr will ask you for sudo privileges. This is normal as schr is installed through [pipx](https://github.com/pypa/pipx).

If you want to install schr manually (which will still require sudo privileges) to understand what is happening under the hood:

* Clone schr to `.schr/` in your home (`~`) folder: 
```sh
git clone https://github.com/LasramR/simple-cpp-hot-reloader.git ~/.schr
```

* Install pipx:
```sh
sudo apt update;
sudo apt install pipx;
```

* Install schr with pipx:
```sh
pipx install -e ~/.schr
```

---

If the installation was successful, open a new terminal and run :

```sh
schr -h
```

It should output:

```
usage: schr

Simple CPP Hot Reloader (schr)

...
```


Note: I am looking for a way to install a binary build of schr with [nuitka](https://nuitka.net/)

## Usage

To use schr with your project, run the following command:

```sh
schr -t <path/to/your/project/built/executable>
```

This command is the bare minimum for schr to start. It monitors your project for changes, recompiles, and links it as needed, producing the specified executable. Maybe it will work, maybe not.

To ensure that schr will be able to build your project, you must pass your project metadata (ie compiler, compiler flags, ...) as arguments in the command.

Here are the arguments that can be used to inform schr:

| Argument | Usage | Description | Default |
| --- | --- | --- | --- |
| -c,--compiler | -c COMPILER | C/C++ compiler executable to use (eg gcc, g++, clang, ...) | g++ |
| -cf,--cflags | -cf="..." | Sets additional flags for the C/C++ compiler (eg -std=c++20, -Wall, ...) | |
| -lf,--lflags | -lf="..." | Sets additional flags for the C/C++ linker (eg -lpthread, -lvulkan, ...) | |
| -od,--obj-dir | -od OBJ_DIR | Specifies the directory where object files (*.o) should be stored. If not provided, object files are outputed next to the source code | |
| -t,--target | -t TARGET | The path for the built executable of your project | |
| -ta,--target-args | -ta="..." | Command-line arguments to pass to your built executable when it is restarted by schr | |
| -m,--mode | -m MODE |  Configures schr behavior using a set of mode characters (see [Modes](#modes)) | CR |
| -d,--debug | -d | Enable schr debug mode which displays compiler/linker commands during execution | Disabled |
| --makefile | --makefile | Outputs the source code for a makefile that can be used to invoke schr with the specified arguments | Disabled |

Thus, if you need to compile your project with clang, you can use the **-c** flag:

```sh
schr -t <path/to/your/project/built/executable> -c clang
```

For a more complete example see [Example](#example).

## [Modes](#modes)

When running schr, you may only want to recompile your project and run it when you are finished working, or you may want to restart your project when a change occurs.

The mode flag **-m**,**--mode** is a combination of the following values : C, R.

* C corresponds to the "Compilation" mode. When enabled, any change to a source file will be instantly recompiled
* R corresponds to the "Restart" mode. When enabled, your project built executable will be restarted every time your project is linked (ie the compilation is done)

You can use both mode a the same time (eg `-m CR`) or only a given one (eg `-m C`).

By default, C and R mode are enabled.

## Cache

After recompiling your project, schr will create a cache file named `.schr.cache` in the directory you have run schr.

This file is used by schr to check if a source file has been successfully compiled. Thus when you run schr for the first time with your project, it will recompile (if "C" mode is enabled) all of your source code to compute the cache.

Moreover, when you make changes to your source code without running schr, the cache file will allow schr to detect which files have been changed since its last execution.

This cache helps speed up subsequent builds and helps skipping unchanged source code.

If you are saving your changes on a remote version control (eg GitHub), you may not want to upload the schr cache. You can omit the cache upload by adding the following line to your `.gitignore` file:

```sh
# schr cache
.schr.cache
```

## [Example](#example)

Let's say we are developing a Vulkan project in c++.

**To compile** our source code we will use g++.

We will be using c++20 features, so we will need to **pass compiler flags** to g++: -std=c++20.

All of our source code is located in a `src` folder, we will need to add this folder to the compiler include path by passing the following compiler flag to g++: -I./src.

Because we are using Vulkan, we will need to **pass linker flags** to g++ to find external dependencies: -lvulkan.

We want to **store the compiled code** (ie *.o object files) in a `bin` folder.

The built project should be **executable** by running a file named `myvulkanapp`. Finally, we would like to **pass arguments to the project executable**, `myvulkanapp` takes a **-m** flags that allows to specify a 3d object to be rendered by the app.

Given our project specs, the following arguments must be pass to schr to successfully build and run our project:
- **-c** g++
- **-cf**="-std=c++20 -I./src"
- **-lf**="-lvulkan"
- **-od** "./bin"
- **-t** myvulkanapp
- **-ta**="-m my3dmodel.obj"

Thus, you will run schr as follows:

```sh
schr -c g++ -cf="-std=c++20 -I./src" -lf="-lvulkan" -od "./bin" -t myvulkanapp -ta="-m my3dmodel.obj"
```

If you don't want schr to restart your project after each execution, you can change schr behavior to "Compilation" only by using the **-m**,**--mode** flag as follows : **-m C**,**--mode C**.

If you never ran schr with your project, it will compile and link your project for the first time to create a compilation cache.

## Uninstall schr

To uninstall schr, run the following command:

```sh
~/.schr/_uninstall.sh
```

Note: if you have installed schr without a single command, be sure that `~/.schr/_uninstall.sh` is executable with:

```sh
chmod +x ~/.schr/_uninstall.sh
```

## Improvements 

* Slow start: I tested schr on a cpp vulkan project with over 60+ (long) files, schr needed at least 20-30 seconds to boot. Even though I am coding on a potato, the initial dependency graph computation could be sped up using multithreading.
* Proper testing: schr is considered stable because it works on my machine. Ideally, I will write unit tests to confirm my thought.
* Maximum parallel operations: add a flag to restrict the maximum number of parallel operations
* Select specifc c preprocessor : add a flag to specify which c pre processor to use when parsing dependencies
