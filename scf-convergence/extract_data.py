#!/usr/bin/env python
from pathlib import Path

import typer
from aiida import load_profile, orm
from rich.progress import track
from rich import print


def cli(scf_group: str, target_directory: Path):
    """Extract the non-converging calculations from a group of `PwBaseWorkChain`s."""
    load_profile()

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
        cj_dir = target_directory / f'pw-{pw_calc.pk}'
        cj_dir.mkdir(exist_ok=True)

        structure.get_pymatgen().to((cj_dir / f'{structure.get_formula()}.cif').as_posix())

        with (cj_dir / 'pw.in').open("w") as handle:
            handle.write(
                pw_calc.base.repository.get_object_content("aiida.in")
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


if __name__ == "__main__":
    typer.run(cli)
