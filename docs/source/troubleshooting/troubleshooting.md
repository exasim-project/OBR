# Troubleshooting
---

## 'File' object has no attribute 'update'
  > Make sure to have only one version of `owls` installed.
  > Furthermore, make sure to install owls via `pip install .` from within the cloned repository.
  > Slightly more explanation in [issue#74](https://github.com/hpsim/OBR/issues/74).

## No such file or directory: 'blockMesh
  > Make sure to have your local openfoam installation sourced.
  > The precompiled binaries from `openfoam2212` do not include the `blockMesh` command. Do **not** install the `openfoam` package as this will lead to other errors, even though the `blockMesh` operation will now be available. Rather compile `openfoam2212` from source, see the [OpenFOAM2212 documentation](https://develop.openfoam.com/Development/openfoam/-/blob/master/doc/Build.md). 

## FOAM FATAL IO ERROR: Wrong token type - expected string, found on line (e.g.) 47: word 'libOGL.so'
  > Make sure to not have conflicting openFOAM installations, e.g. `openfoam2212` and `openfoam` (both installed via `apt install`)
  > Remove the `openfoam` installation (`apt uninstall openfoam`). If this error happened after installing `openfoam` due to a missing operation, e.g. `blockMesh` see [this issue](#no-such-file-or-directory-blockmesh)

## 'cp: cannot access' during fetchCase
  > This error can stem from setting `LidDrivenCavityS` to e.g. `/tmp`.
  > It will likely also throw a `flow.errors.UserOperationError` later on.
  > Try `unset LidDrivenCavityS` or `export LidDrivenCavityS=/pathTo/existing/empty/folder`