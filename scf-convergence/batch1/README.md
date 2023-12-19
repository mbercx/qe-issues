# `batch1` - Reruns from LUMI-C hero run on Piz Daint

This is a selection of 100 calculations based on previous failures from the LUMI-C hero run.
Some notes:

* These still use the "old" protocol, i.e. with cold smearing 0.01 Ry
* The initial `mixing_beta` is set to 0.4.
  The `PwBaseWorkChain` has also tried reducing the `mixing_beta` to 0.2 and 0.1, but with no success.
* All the structures here are rather small (< 15 atoms), and run spin-polarised.
