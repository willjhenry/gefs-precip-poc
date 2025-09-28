from setuptools import find_packages, setup


def get_all_requires():
    reqs = []
    with open("requirements.txt") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # ignore local/editable/includes and pip flags
            if line.startswith(("-e", "-r", "--")):
                continue
            reqs.append(line)
    return reqs


setup(
    name="hydro",
    version="0.1.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=get_all_requires(),
    author="William Henry",
    description="Proof-of-concept for GEFS precipitation post-processing",
)
