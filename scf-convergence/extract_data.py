#!/usr/bin/env python
"""Messy scripts to extract data regarding SCF convergence."""
from calendar import c
from pathlib import Path
from typing import Optional
from aiida.cmdline.utils.decorators import with_dbenv

import numpy

from matplotlib import pyplot as plt

import typer
from aiida import orm
from rich.progress import track
from rich import print
from aiida_quantumespresso.calculations.pw import PwCalculation


app = typer.Typer()


def plot_scf_accuracy(pw_base, axis=None, label=None):
    """Plot the scf accuracy of a PwBaseWorkChain."""

    def get_actions(pw_base):
        """Get actions from log messages."""

        string_action_map = {
            'beta': 'Beta',
            'slope': 'Restart',
            'local-TF': 'local-TF',
            'diagonalization': 'diag',
        }
        action_logs = [log.message for log in orm.Log.objects.get_logs_for(pw_base) if 'Action' in log.message]

        actions = []
        for action_log in action_logs:
            for string, action in string_action_map.items():
                if string in action_log:
                    actions.append(action)
        return actions

    actions = get_actions(pw_base)
    scf_accuracy_all = numpy.array([])
    restarts = []

    for pw in pw_base.called:
        if pw.process_class == PwCalculation:
            pw_n_scf_steps = pw.outputs.output_parameters.get_dict()['convergence_info']['scf_conv']['n_scf_steps']
            restarts.append(pw_n_scf_steps)
            try:
                scf_accuracy_all = numpy.hstack((scf_accuracy_all, pw.tools.get_scf_accuracy(-1)))
            except (KeyError, ValueError):
                scf_accuracy_all = numpy.hstack((scf_accuracy_all, numpy.zeros(pw_n_scf_steps)))

    if axis is None:
        axis = plt.gca()

    axis.plot(numpy.log(scf_accuracy_all))
    axis.set_ylabel('log(scf accuracy)')

    for restart, action in zip(numpy.cumsum(restarts)[:-1], actions):
        axis.axvline(x=restart + 1, color='r', linestyle='-')    
        axis.text(
            restart, axis.get_ylim()[1] + 0.03 * (axis.get_ylim()[1] - axis.get_ylim()[0]),
            action, color='r', horizontalalignment="center"
        )

    if label is not None:
        axis.text(
            axis.get_xlim()[0] * 0.05, axis.get_ylim()[1] - 0.05 * (axis.get_ylim()[1] - axis.get_ylim()[0]),
            label, color='b', horizontalalignment="left", verticalalignment="top", fontsize=8,
            bbox=dict(facecolor='white', edgecolor='black', pad=2)
        )


def get_total_nsteps(pw_base):
    """Get the total number of steps of a PwBaseWorkChain."""
    nsteps = 0
    for pw in pw_base.called:
        if pw.process_class == PwCalculation:
            nsteps += pw.outputs.output_parameters.get_dict()['convergence_info']['scf_conv']['n_scf_steps']
    return nsteps


def get_total_walltime(pw_base):
    """Get the total walltime of a PwBaseWorkChain."""
    walltime = 0
    for pw in pw_base.called:
        if pw.process_class == PwCalculation:
            walltime += pw.outputs.output_parameters.get_dict()['wall_time_seconds']
    return walltime


def report(reference_pwbase, candidate_pwbase):
    """Print a report of the reference and candidate PwBaseWorkChain."""
    print(f'Reference PwBaseWorkChain: {reference_pwbase.pk}')
    print(f'Candidate PwBaseWorkChain: {candidate_pwbase.pk}')

    print(f"Ref. Energy: {reference_pwbase.outputs.output_parameters.get_dict()['energy']}")
    print(f"Can. Energy: {candidate_pwbase.outputs.output_parameters.get_dict()['energy']}")

    print(f"Ref. Total magnetization: {reference_pwbase.outputs.output_parameters.get_dict()['total_magnetization']}")
    print(f"Can. Total magnetization: {candidate_pwbase.outputs.output_parameters.get_dict()['total_magnetization']}")    


def get_files(cj_dir, structure, pw_calc, retrieved):
    """Get the files from a PwCalculation."""

    cj_dir.mkdir(exist_ok=True)

    structure.get_pymatgen().to((cj_dir / f'{structure.get_formula()}.cif').as_posix())

    with (cj_dir / 'pw.in').open("w") as handle:
        handle.write(
            pw_calc.base.repository.get_object_content("aiida.in")
        )

    with (cj_dir / 'submit.sh').open("w") as handle:
        handle.write(
            pw_calc.base.repository.get_object_content("_aiidasubmit.sh")
        )

    pseudo_dir = cj_dir / "pseudo"
    pseudo_dir.mkdir(exist_ok=True)

    for pseudo in pw_calc.inputs.pseudos.values():
        with (pseudo_dir / pseudo.filename).open("w") as handle:
            handle.write(pseudo.get_content())

    with (cj_dir / 'pw.out').open("w") as handle:
        handle.write(
            retrieved.base.repository.get_object_content("aiida.out")
        )


@app.command()
@with_dbenv()
def failed(scf_group: str, target_directory: Path):
    """Extract the non-converging calculations from a group of `PwBaseWorkChain`s."""

    target_directory.mkdir(exist_ok=True)

    query = orm.QueryBuilder()

    query.append(
        orm.Group, filters={"label": scf_group}, tag="group"
    ).append(
        orm.WorkChainNode, with_group="group", tag="base",
        filters={'attributes.exit_status': 401}
    ).append(
        orm.CalcJobNode,
        with_incoming="base",
        filters={'attributes.exit_status': 410},
        edge_filters={"label": "iteration_01"},
        tag="pw",
        project="*",
    ).append(
        orm.StructureData, with_outgoing="pw", project="*"
    ).append(
        orm.FolderData, with_incoming='pw', project='*'
    )
    print(f'[bold blue]Info:[/] Found {query.count()} calculations.')

    for pw_calc, structure, retrieved in track(
        query.all(), description="Extracting data from query..."
    ):
        source_db = structure.extras['source_db']
        source_id = structure.extras['source_id']
    
        cj_dir = target_directory / f'{source_db}-{source_id}'

        get_files(cj_dir, structure, pw_calc, retrieved)


@app.command()
@with_dbenv()
def fixed(ref_group: str, cand_group:str, target_directory: Optional[Path] = None):

    if target_directory:
        target_directory.mkdir(exist_ok=True)

    results_dict = {
        'both_failed': 0,
        'both_converged': 0,
        'only_ref_converged': 0,
        'only_can_converged': 0,
    }
    nstep_dict = {
        'reference': 0,
        'candidate': 0,
    }
    walltime_dict = {
        'reference': 0,
        'candidate': 0,
    }

    for candidate_pwbase in track(
        orm.load_group(cand_group).nodes,
        description="Analyzing"
    ):

        if not candidate_pwbase.is_finished:
            continue

        query = orm.QueryBuilder()

        query.append(
            orm.Group, filters={"label": ref_group}, tag="group"
        ).append(
            orm.WorkChainNode, with_group="group", tag="workchain",
            filters={"and": [
                {"extras.source_db": candidate_pwbase.extras["source_db"]},
                {"extras.source_id": candidate_pwbase.extras["source_id"]},
            ]}
        )
        try:
            reference_pwbase = query.first()[0]
        except TypeError:
            print(f'[bold red]Error:[\] No reference found for {candidate_pwbase}')
            continue

        if not reference_pwbase.is_finished:
            continue

        if reference_pwbase.is_finished_ok and candidate_pwbase.is_finished_ok:
            results_dict['both_converged'] += 1
        elif not reference_pwbase.is_finished_ok and not candidate_pwbase.is_finished_ok:
            print(f'Both failed - Ref. PK: {reference_pwbase.pk} Cand. PK: {candidate_pwbase.pk}')
            results_dict['both_failed'] += 1
        elif reference_pwbase.is_finished_ok:
            results_dict['only_ref_converged'] += 1
            print(f'Cand. failed - Ref. PK: {reference_pwbase.pk} Cand. PK: {candidate_pwbase.pk}')
        elif candidate_pwbase.is_finished_ok:
            results_dict['only_can_converged'] += 1
            print(f'Ref. failed - Ref. PK: {reference_pwbase.pk} Cand. PK: {candidate_pwbase.pk}')

            if target_directory:

                structure = candidate_pwbase.inputs.pw.structure

                source_db = structure.extras['source_db']
                source_id = structure.extras['source_id']

                struc_dir = target_directory / f'{source_db}-{source_id}'
                struc_dir.mkdir(exist_ok=True)
                (struc_dir / 'reference').mkdir(exist_ok=True)
                (struc_dir / 'candidate').mkdir(exist_ok=True)

                for link in reference_pwbase.base.links.get_outgoing().all():
                    if isinstance(link.node, orm.CalcJobNode):
                        cj_dir = struc_dir / 'reference' / link.link_label
                        get_files(cj_dir, structure, link.node, link.node.outputs.retrieved)

                for link in candidate_pwbase.base.links.get_outgoing().all():
                    if isinstance(link.node, orm.CalcJobNode):
                        cj_dir = struc_dir / 'candidate' / link.link_label
                        get_files(cj_dir, structure, link.node, link.node.outputs.retrieved)

                fig, ax = plt.subplots(2, 1, figsize=(6, 4), sharex=True)

                plot_scf_accuracy(reference_pwbase, ax[0], label=ref_group)
                plot_scf_accuracy(candidate_pwbase, ax[1], label=cand_group)

                ax[1].set_xlabel('Iteration')

                fig.savefig(struc_dir / 'scf_acc_comparison.png', dpi=300)

        try:
            nstep_dict['reference'] += get_total_nsteps(reference_pwbase)
            nstep_dict['candidate'] += get_total_nsteps(candidate_pwbase)
        except Exception as e:
            print(e)

        try:
            walltime_dict['reference'] += get_total_walltime(reference_pwbase)
            walltime_dict['candidate'] += get_total_walltime(candidate_pwbase)
        except Exception as e:
            print(candidate_pwbase.pk, e)

    print('Reference group:', ref_group)
    print('Candidate group:', cand_group)
    print()
    print('convergence', results_dict)
    print('nsteps', nstep_dict)
    print('walltimes', walltime_dict)


if __name__ == "__main__":
    app()
