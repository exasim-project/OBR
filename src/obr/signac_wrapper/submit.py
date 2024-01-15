import shutil
import os
import logging

from pathlib import Path
from signac.job import Job
from typing import Union

from .operations import OpenFOAMProject

def submit_impl(
    project: OpenFOAMProject,
    jobs: list[Job],
    operations: list[str],
    template: Union[str, None],
    account: Union[str, None],
    partition: Union[str, None],
    pretend: bool,
    bundling_key: Union[str, None],
    scheduler_args: str,
):
    template_target_path = Path(project.path) / "templates/script.sh"
    template_src_path = Path(template)

    if not template_src_path.exists():
        raise FileNotFoundError(template)

    if template and template_target_path.exists():
        shutil.rmtree(template_target_path.parent)

    if template:
        os.makedirs(template_target_path.parent, exist_ok=True)
        shutil.copyfile(template_src_path, template_target_path)

    project._entrypoint = {"executable": "", "path": "obr"}

    # TODO find a signac way to do that
    cluster_args = {
        "partition": partition,
        "pretend": pretend,
        "account": account,
    }

    # TODO improve this using regex
    if scheduler_args:
        split = scheduler_args.split(" ")
        for i in range(0, len(split), 2):
            cluster_args.update({split[i]: split[i + 1]})

    if bundling_key:
        bundling_values = get_values(jobs, bundling_key)
        for bundle_value in bundling_values:
            selected_jobs: list[Job] = [
                j for j in project if bundle_value in list(j.sp().values())
            ]
            logging.info(f"Submit bundle {bundle_value} of {len(selected_jobs)} jobs")
            ret_submit = (
                project.submit(
                    jobs=selected_jobs,
                    bundle_size=len(selected_jobs),
                    names=operations,
                    **cluster_args,
                )
                or ""
            )
            logging.info("Submission response" + str(ret_submit))
            time.sleep(15)
    else:
        logging.info(f"Submitting {len(jobs)} individual jobs")
        ret_submit = project.submit(
            jobs=jobs,
            names=operations,
            **cluster_args,
        )
        logging.info(ret_submit)
