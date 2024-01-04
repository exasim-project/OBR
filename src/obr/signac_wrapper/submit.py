import shutil
import os

from signac.job import Job


def submit_impl(
    project,
    jobs,
    operations: list[str],
    template: Union[str, None],
    account: Union[str, None],
    partition: Union[str, None],
    pretend: bool,
    bundling_key: Union[str, None],
    scheduler_args: str,
):
    template_target_path = Path("templates/script.sh")
    template_src_path = Path(template)

    if not template_src_path.exists():
        raise FileNotFoundError(template)

    if template and template_target_path.exists():
        shutil.rmtree(str(template_target_path))

    if template:
        os.makedirs("templates", exist_ok=True)
        shutil.copytree(str(template_target_path))

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
            logging.info(f"submit bundle {bundle_value} of {len(selected_jobs)} jobs")
            ret_submit = (
                project.submit(
                    jobs=selected_jobs,
                    bundle_size=len(selected_jobs),
                    names=operations,
                    **cluster_args,
                )
                or ""
            )
            logging.info("submission response" + str(ret_submit))
            time.sleep(15)
    else:
        # logging.info(f"submitting {len(jobs)} individual jobs")
        # import cProfile
        # import pstats

        # with cProfile.Profile() as pr:
        ret_submit = project.submit(
            jobs=jobs,
            names=operations,
            **cluster_args,
        )
        logging.info(ret_submit)

    # stats = pstats.Stats(pr)
    # stats.sort_stats(pstats.SortKey.TIME)
    # # stats.print_stats()
    # stats.dump_stats(filename="needs_profiling.prof")

    # print(project.scheduler_jobs(TestEnvironment.get_prefix(runSolver)))
    # print(list(project.scheduler_jobs(TestEnvironment.get_scheduler())))
