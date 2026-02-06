from pathlib import Path
from typing import List

BASE_DIR = Path(r"T:\architecture archives\Target\03 Projects")
PROJECT_SUBPATH = Path(r"01_CDS\01_CURRENT\01_REVIT")
ARCHIVE_SUBPATH = Path(r"01_CDS\02_ARCHIVE")
OUTPUT_FILE = Path("revit_scan_report.txt")

report_lines: List[str] = []


def add_line(line: str = "") -> None:
    """Append a line to both stdout and the report buffer."""
    print(line)
    report_lines.append(line)


def build_archive_tree(root: Path) -> List[str]:
    """Return a tree-style listing of folders and .rvt files under root."""
    lines: list[str] = []
    if not root.exists():
        return [f"Archive directory not found -> {root}"]

    lines.append(f"Tree for {root}:")

    def safe_iterdir(directory: Path) -> list[Path]:
        try:
            return list(directory.iterdir())
        except PermissionError:
            return []

    def walk(directory: Path, prefix: str = "") -> None:
        entries: List[Path] = [
            entry
            for entry in safe_iterdir(directory)
            if entry.is_dir() or entry.suffix.lower() == ".rvt"
        ]
        entries.sort(key=lambda p: (not p.is_dir(), p.name.lower()))
        for idx, entry in enumerate(entries):
            connector = "└──" if idx == len(entries) - 1 else "├──"
            if entry.is_dir():
                lines.append(f"{prefix}{connector} {entry.name}/")
                extension = "    " if idx == len(entries) - 1 else "│   "
                walk(entry, prefix + extension)
            else:
                lines.append(f"{prefix}{connector} {entry}")

    walk(root)
    if len(lines) == 1:
        lines.append("  (no folders or .rvt files found)")
    return lines


years_scanned = 0
year_dirs_missing = 0
projects_checked = 0
projects_with_rvt = 0
total_rvt_files = 0

add_line("Revit scan")
add_line("==============================")

for year in range(2022, 2026):
    year_dir = BASE_DIR / str(year)
    add_line(f"\nYear {year}")
    add_line("-" * 40)
    if not year_dir.exists():
        add_line(f"{year}: year directory not found -> {year_dir}")
        year_dirs_missing += 1
        continue

    years_scanned += 1
    project_dirs = sorted(p for p in year_dir.iterdir() if p.is_dir())
    if not project_dirs:
        add_line(f"{year}: no project folders inside {year_dir}")
        continue

    for project_dir in project_dirs:
        projects_checked += 1
        label = f"{year} | {project_dir.name}"
        add_line(f"{label}")
        target_dir = project_dir / PROJECT_SUBPATH
        rvt_files: List[Path] = []
        if not target_dir.exists():
            add_line(f"  Current folder missing -> {target_dir}")
        else:
            rvt_files = sorted(target_dir.glob("*.rvt"), key=lambda p: p.name.lower())

        if rvt_files:
            projects_with_rvt += 1
            total_rvt_files += len(rvt_files)
            add_line(
                f"  Found {len(rvt_files)} .rvt file(s) within {target_dir}"
            )
            for file in rvt_files:
                add_line(f"    - {file}")
        else:
            add_line(f"  No .rvt files in {target_dir}")
            archive_dir = project_dir / ARCHIVE_SUBPATH
            add_line(f"  Checking archive -> {archive_dir}")
            for tree_line in build_archive_tree(archive_dir):
                add_line(f"    {tree_line}")

add_line("\nTotals")
add_line("------")
add_line(f"Years scanned: {years_scanned}")
add_line(f"Year directories missing: {year_dirs_missing}")
add_line(f"Projects checked: {projects_checked}")
add_line(f"Projects with .rvt files: {projects_with_rvt}")
add_line(f"Total .rvt files found (01_REVIT only): {total_rvt_files}")

OUTPUT_FILE.write_text("\n".join(report_lines) + "\n", encoding="utf-8")
print(f"\nReport saved to {OUTPUT_FILE.resolve()}")
