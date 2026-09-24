# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0
#
# Maintainer: Andy Curtis <contactandyc@gmail.com>

import graphlib
from pathlib import Path
from typing import Dict, Set, List
from rich.console import Console

from natural.normalizer.parser import NaturalParser
from natural.normalizer.lowering import SemanticLoweringPass
from natural.normalizer.workspace import Workspace
from natural.ir.models import NaturalModule
from natural.codegen.python_emitter import PythonEmitter

console = Console()

class ProjectBuilder:
    def __init__(self, workspace_dir: Path):
        self.workspace_dir = workspace_dir
        self.workspace = Workspace(include_dirs=[workspace_dir])
        self.parser = NaturalParser()

        # Caches
        self.ir0_cache: Dict[str, NaturalModule] = {}
        self.dependency_graph: Dict[str, Set[str]] = {}

    def scan_workspace(self):
        """Scans the directory, parses to IR0, and extracts dependencies."""
        for file_path in self.workspace_dir.glob("*.*"):
            # We only build dependency nodes for executable/data areas, ignoring flat text files
            if file_path.suffix.lower() not in ('.nsp', '.nsn', '.nsa', '.ddm'):
                continue

            module_name = file_path.stem.upper()

            # Use the Workspace's caching logic to load the file
            if file_path.suffix.lower() == '.ddm':
                area = self.workspace.get_ddm(module_name)
                # DDM's have no outgoing dependencies
                self.dependency_graph[module_name] = set()
                continue
            elif file_path.suffix.lower() == '.nsa':
                # Force loading into workspace cache
                area = self.workspace.get_data_area(module_name, scope=None)
                self.dependency_graph[module_name] = set()
                continue

            # Parse programs/subprograms to IR0
            try:
                ir0 = self.parser.parse_file(file_path)
                self.ir0_cache[module_name] = ir0

                # Extract edges for the DAG
                deps = set()
                for area in ir0.data_areas:
                    deps.add(area.name.upper())
                for inc in ir0.includes:
                    deps.add(inc.upper())

                # Note: To be perfectly robust, you would also traverse `ir0.body`
                # looking for `CallnatStatement` and `FindStatement` to extract subprograms and views.
                for stmt in ir0.body:
                    if getattr(stmt, "statement_type", "") == "FIND":
                        deps.add(stmt.view_name.upper())
                    elif getattr(stmt, "statement_type", "") == "CALLNAT":
                        deps.add(stmt.subprogram_name.upper())

                self.dependency_graph[module_name] = deps
            except Exception as e:
                console.print(f"[yellow]Warning: Could not extract dependencies for {module_name}: {e}[/yellow]")

    def get_build_order(self) -> List[str]:
        """Returns the modules in topological compilation order."""
        sorter = graphlib.TopologicalSorter(self.dependency_graph)
        try:
            return list(sorter.static_order())
        except graphlib.CycleError as e:
            console.print(f"[bold red]Circular Dependency Detected:[/bold red] {e}")
            raise

    def compile_project(self):
        """Compiles all modules strictly following the DAG order."""
        self.scan_workspace()
        build_order = self.get_build_order()

        console.print(f"[bold cyan]Compilation Order:[/bold cyan] {' -> '.join(build_order)}")

        for module_name in build_order:
            # We only generate Python for executable modules, not bare data areas
            if module_name not in self.ir0_cache:
                continue

            console.print(f"Compiling {module_name}...")
            ir0 = self.ir0_cache[module_name]

            # The workspace cache guarantees the dependencies are pre-loaded
            semantic_pass = SemanticLoweringPass(ir0, workspace=self.workspace)
            ir1 = semantic_pass.lower()

            emitter = PythonEmitter(ir1)
            py_source = emitter.generate()

            # Write to a build directory
            out_file = self.workspace_dir / "build" / f"{module_name.lower()}.py"
            out_file.parent.mkdir(exist_ok=True)
            out_file.write_text(py_source, encoding="utf-8")
