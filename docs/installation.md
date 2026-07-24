# Installation

## Requirements

- Python 3.12 or higher
- pip or uv package manager
- For Windows: Visual C++ Redistributable (usually pre-installed)

## Using pip

```bash
pip install epyraw
```

## Using uv (recommended)

```bash
uv pip install epyraw
```

## Development Installation

For development, clone the repository and install with dev dependencies:

```bash
git clone https://github.com/hechth/epyraw.git
cd epyraw

# Using uv
uv sync --dev

# Or using pip
pip install -e ".[dev]"
```

## Verifying Installation

Test that the package is installed correctly:

```python
from epyraw import RawFile, Device

print(f"epyraw version: {RawFile.__module__}")
```

## Troubleshooting

### .NET Runtime Issues

If you encounter issues with .NET runtime:

1. Ensure you have the latest Visual C++ Redistributable on Windows
2. On Linux, ensure libicu and other dependencies are installed
3. Try setting the runtime explicitly:

```python
from epyraw import set_runtime
set_runtime("coreclr")  # or "mono"
```

### Missing RawFileReader DLLs

The package includes the required .NET assemblies. If you encounter missing DLL errors:

1. Reinstall the package
2. Check that antivirus software isn't blocking the DLLs
3. Verify the DLLs are in the package location:
   ```
   site-packages/epyraw/runtimes/net8old/
   ```
