# How to build mGear

## Prerequisites

Git (of course)

Python 2.7

SCons

Maya 2014 ~ 2018 (*)

A C++ compiler: (*)
- gcc on linux
- clang on OSX
- Visual Studio on windows (**)

(*) Only when building the plugins

(**) The version should match the one used by the target Maya version

## Step by step process

1. Clone the repository and initialize it

```
$ git clone git@github.com:mgear-dev/mgear_dist.git
$ cd mgear_dist
$ git submodule update --init
$ git submodule foreach --recursive git checkout master
```

2. Checkout the desired branch or tag

- **develop** : latest developments 
- **master** : latest official release
- **RB-x.x** : latest version in x.x series (i.e. 2.2.5 in RB-2.2)

```
$ git submodule foreach --recursive git checkout develop
$ git submodule foreach git pull origin develop
```

3. Compile

The available targets are:
- **mgear_core** : Only mgear python module.
- **mgear_solvers** : Solvers maya plugin.
- **cvwrap** : cvwrap maya plugin.
- **mgear** : everything (*default*)

```
$ scons with-maya=2017
...
(let it cook)
```

To show all available build options:

```$ scons -h```




