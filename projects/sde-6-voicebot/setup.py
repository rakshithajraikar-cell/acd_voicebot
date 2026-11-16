from setuptools import setup, find_packages

setup(
    name="sde6-voicebot-w3",
    version="1.0.0",
    description="Academiaai AI Voicebot - Team SDE 6 Workstream W3 Context and Reasoning",
    author="Prathibhashree K",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=3.10",
)
