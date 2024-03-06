import shutil
import os

from pathlib import Path
from signac.job import Job
from typing import Union
from tqdm import tqdm

from .operations import OpenFOAMProject, basic_eligible
from .labels import final
from ..core.logger_setup import logger


def submit_impl(
    project: OpenFOAMProject,
    jobs: list[Job],
    operations: list[str],
    template: Union[str, None],
    account: Union[str, None],
    partition: Union[str, None],
    time: Union[str, None],
    pretend: bool,
    bundling_key: Union[str, None],
    max_queue_size: Union[str, None],
    scheduler_args: str,
    skip_eligible_check=False,
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

    # let submit cal obr run -o instead of signac run -o
    project.set_entrypoint({"executable": "", "path": "obr"})

    # TODO find a signac way to do that
    cluster_args = {
        "partition": partition,
        "pretend": pretend,
        "account": account,
        "walltime": time,
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
            logger.info(f"Submit bundle {bundle_value} of {len(eligible_jobs)} jobs")
            ret_submit = (
                project.submit(
                    jobs=selected_jobs,
                    bundle_size=len(selected_jobs),
                    names=operations,
                    **cluster_args,
                )
                or ""
            )
            logger.info("Submission response" + str(ret_submit))
            time.sleep(15)
    else:
        eligible_jobs = []
        for operation in operations:
            if operation == "runParallelSolver":
                for job in tqdm(jobs):
                    if final(job):
                        eligible_jobs.append(job)
            else:
                logger.info(f"Collecting eligible jobs for operation: {operation}.")
                for job in tqdm(jobs):
                    if basic_eligible(job, operation):
                        eligible_jobs.append(job)

        logger.info(
            f"Submitting operations {operations}. In total {len(eligible_jobs)} of"
            f" {len(jobs)} individual jobs.\nEligible jobs"
            f" {[j.id for j in eligible_jobs]}"
        )

        bundle_size = 1
        if len(eligible_jobs) > max_queue_size:
            logger.warning(
                "Found more eligible jobs than maximum allowed queue size of"
                f" {max_queue_size}. Bundling jobs together. This might fail if jobs"
                " request different resources. For more fine grained control use"
                " --bundling_key option."
            )
            bundle_size = int(len(eligible_jobs) / max_queue_size)

        ret_submit = project.submit(
            jobs=eligible_jobs if not skip_eligible_check else jobs,
            names=operations,
            bundle_size=bundle_size,
            **cluster_args,
        )
        logger.info(ret_submit)
    logger.success("Successfully submitted")
