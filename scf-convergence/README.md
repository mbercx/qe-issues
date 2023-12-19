# SCF convergence failures

Collection of SCF runs with Quantum ESPRESSO where the electronic minimization cycle failed to converge.
For each structure in each batch, the directory tree is as follows:

```
└── <STRUCTURE DATABASE & ID>
    ├── <FORMULA>.cif
    ├── iteration_01
    │   ├── pw.in
    │   └── pw.out
    ├── iteration_02
    │   ├── pw.in
    │   └── pw.out
    └── ...
```

The iterations here represent separate runs performed by the AiiDA `PwBaseWorkChain` with attempts to fix the electronic convergence by e.g. reducing the `mixing_beta`.

Below is a short description of each batch.

## `batch1` - Reruns from LUMI-C hero run on Piz Daint

This is a selection of +100 structures that failed to converge during the LUMI-C hero run.
Some notes:

* These still use the "old" `moderate` protocol, i.e. with cold smearing 0.01 Ry, and SSSP v1.2.
* The initial `mixing_beta` is set to 0.4.
  The `PwBaseWorkChain` has also tried reducing the `mixing_beta` to 0.2 and 0.1, but with no success.
* All the structures here are rather small (< 15 atoms), and are run spin-polarised.
* These are GPU runs on Piz Daint.

## `batch2-500step`

This is a smaller set of structures (with some overlap) where we used the new version of the `efficiency` protocol: `cold` smearing of 0.02 Ry and SSSP v1.3 (the latter shouldn't matter since v1.3 just adds pseudos for the actinides).
These are reference runs where we set an excessive `electron_maxstep` of 500 to give the SCF plenty of steps to convergence.

## `batch2-fixed`

Here we present attempts from the new approaches of the `PwBaseWorkChain` to fix the SCF convergence, see:

https://github.com/mbercx/aiida-quantumespresso/blob/4d15f6db50a28a7bb324201954cef9ddddeefd67/src/aiida_quantumespresso/workflows/pw/base.py#L567-L656

In short, now the work chains:

1. Always increases the number of bands upon the first SCF failure (TODO: this should probably be disable for `occupations` = `fixed`).
2. Checks the slope of the `scf_accuracy` and simply restarts in case its log < -0.1.
3. Checks if the structure is lower-dimensional and switch to `local-TF` smearing if still using `plain`.
4. Tries different diagonalizations.
   This seems somewhat simplistic and trying all of them is probably overkill, but [in some cases](https://github.com/mbercx/qe-issues/blob/main/scf-convergence/batch2-fixed/mpds-S1638949/scf_acc_comparison.png) the 4th change in diagonalization approach suddenly makes the calculation converge.
5. Finally, try to half the `mixing_beta` if it is above 0.1.

The directory structure is slightly different:

```
└── <STRUCTURE DATABASE & ID>
    ├── <FORMULA>.cif
    ├── candidate
    │   ├── iteration_01
    │   │   ├── pw.in
    │   │   └── pw.out
    │   └── iteration_02
    │       ├── pw.in
    │       └── pw.out
    ├── reference
    │   └── iteration_01
    │       ├── pw.in
    │       └── pw.out
    └── scf_acc_comparison.png
```

The `candidate` here is our new `PwBaseWorkChain` error handler approach, the `reference` is the 500 step run described above.
The `scf_acc_comparison.png` plot shows the evolution of the `scf_accuracy` for both reference and candidate.