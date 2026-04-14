from setuptools import setup, find_packages

setup(
    name="context-distiller",
    version="2.0.0",
    packages=find_packages(),
    install_requires=[
        "pydantic>=2.0.0",
        "fastapi>=0.100.0",
        "uvicorn>=0.23.0",
        "click>=8.0.0",
        "psutil>=5.9.0",
        "pyyaml>=6.0",
        "markitdown>=0.0.1a2",
        "PyMuPDF>=1.23.0",
        "python-docx>=1.0.0",
        "opencv-python-headless>=4.8.0",
        "Pillow>=10.0.0",
    ],
    extras_require={
        "gpu": [
            "torch>=2.0.0",
            "transformers>=4.30.0",
            "onnxruntime-gpu>=1.15.0",
            "docling>=1.0.0",
        ],
        "mem0": ["mem0ai>=0.1.0"],
        "full": [
            "torch>=2.0.0",
            "transformers>=4.30.0",
            "onnxruntime-gpu>=1.15.0",
            "docling>=1.0.0",
            "mem0ai>=0.1.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "context-distiller=context_distiller.api.cli.main:cli",
        ],
    },
)
