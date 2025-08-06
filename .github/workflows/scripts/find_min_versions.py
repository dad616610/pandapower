import subprocess
import json
import argparse
import os
import logging
from packaging.requirements import Requirement
from packaging.version import Version, parse

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger()

def run_command(cmd):
    try:
        result = subprocess.run(
            cmd, 
            shell=True, 
            check=True,
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            text=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed: {cmd}\nError: {e.stderr}")
        raise

def get_available_versions(package):
    try:
        output = run_command(f"uv pip index versions {package} --format json")
        data = json.loads(output)
        return sorted([Version(v) for v in data["versions"] if not Version(v).is_prerelease])
    except Exception as e:
        logger.error(f"Failed to get versions for {package}: {str(e)}")
        return []

def test_environment(constraints):
    constraints_file = "min_versions_constraints.txt"
    with open(constraints_file, "w") as f:
        for pkg, ver in constraints.items():
            f.write(f"{pkg}=={ver}\n")
    
    try:
        # Install with current constraints
        run_command("uv pip install -c min_versions_constraints.txt . --resolution=lowest")
        
        # Run tests
        test_script = ".github/scripts/test_project.sh"
        if os.path.exists(test_script):
            run_command(f"bash {test_script}")
        else:
            run_command("pytest tests/")  # Fallback test command
        return True
    except Exception:
        return False
    finally:
        if os.path.exists(constraints_file):
            os.remove(constraints_file)

def binary_search_min_version(package, base_constraints, python_version):
    versions = get_available_versions(package)
    if not versions:
        logger.warning(f"No versions found for {package}, skipping")
        return None

    low, high = 0, len(versions) - 1
    min_working_version = None

    while low <= high:
        mid = (low + high) // 2
        candidate_ver = versions[mid]
        constraints = base_constraints.copy()
        constraints[package] = str(candidate_ver)
        
        logger.info(f"Testing {package}=={candidate_ver} (Python {python_version})")
        
        if test_environment(constraints):
            min_working_version = candidate_ver
            high = mid - 1  # Try lower version
        else:
            low = mid + 1  # Try higher version
    
    return min_working_version

def get_direct_dependencies():
    """Get direct dependencies with their declared minimum versions"""
    try:
        # Use uv pip freeze with direct resolution
        reqs = run_command("uv pip freeze --exclude-newer=now --resolution=lowest-direct")
        return {
            Requirement(line.split("==")[0]).name: line.split("==")[1]
            for line in reqs.splitlines()
        }
    except Exception:
        # Fallback to parsing requirements.txt
        with open("requirements.txt") as f:
            return {
                Requirement(line).name: Requirement(line).specifier[0].version
                for line in f if not line.strip().startswith(("#", "-e"))
            }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--python-version", required=True)
    args = parser.parse_args()
    
    logger.info(f"Finding minimal versions for Python {args.python_version}")
    
    constraints = get_direct_dependencies()
    results = {}
    
    # Process dependencies in safe order (alphabetical)
    for package in sorted(constraints.keys()):
        logger.info(f"\nProcessing {package}...")
        min_ver = binary_search_min_version(package, constraints, args.python_version)
        if min_ver:
            constraints[package] = str(min_ver)
            results[package] = str(min_ver)
            logger.info(f"✅ Minimal version: {min_ver}")
        else:
            results[package] = constraints[package]
            logger.warning(f"❌ Using fallback version: {constraints[package]}")

    # Save results
    output_file = f"min_versions_{args.python_version}.txt"
    with open(output_file, "w") as f:
        for pkg, ver in results.items():
            f.write(f"{pkg}=={ver}\n")
    
    logger.info(f"Results saved to {output_file}")

if __name__ == "__main__":
    main()
