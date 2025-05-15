"""
Directed Acyclic Graph (DAG) representation of operation dependencies.

This module provides functionality for:
1. Building a DAG from a query plan
2. Detecting cycles in the dependency graph
3. Determining execution order (topological sort)
4. Visualizing the DAG
"""

import logging
from typing import Dict, List, Any, Set, Tuple, Optional
import networkx as nx
import matplotlib.pyplot as plt
from io import BytesIO
import base64
import os
from pathlib import Path

# Configure logging
logger = logging.getLogger(__name__)

class OperationDAG:
    """
    Directed Acyclic Graph (DAG) representation of operation dependencies
    
    This class builds a DAG from a query plan and provides methods for
    analyzing and visualizing the dependency structure.
    """
    
    def __init__(self, plan):
        """
        Initialize the DAG from a query plan
        
        Args:
            plan: QueryPlan instance
        """
        self.plan = plan
        self.graph = self._build_graph()
        
        # Create NetworkX graph for advanced algorithms
        self.nx_graph = nx.DiGraph()
        self._build_nx_graph()
    
    def _build_graph(self) -> Dict[str, List[str]]:
        """
        Build adjacency list representation of the graph
        
        Returns:
            Dictionary mapping operation IDs to lists of dependent operation IDs
        """
        # Create adjacency list with empty lists for all operations
        graph = {op.id: [] for op in self.plan.operations}
        
        # Add edges based on dependencies
        for op in self.plan.operations:
            # For each operation that depends on this one, add an edge
            for other_op in self.plan.operations:
                if op.id in other_op.depends_on:
                    graph[op.id].append(other_op.id)
        
        return graph
    
    def _build_nx_graph(self) -> None:
        """Build NetworkX graph for more advanced algorithms"""
        # Add nodes
        for op in self.plan.operations:
            self.nx_graph.add_node(op.id, label=f"{op.__class__.__name__}\n{op.source_id}")
        
        # Add edges
        for op in self.plan.operations:
            for dep_id in op.depends_on:
                self.nx_graph.add_edge(dep_id, op.id)
    
    def has_cycles(self) -> bool:
        """
        Check if the graph has cycles
        
        Returns:
            True if the graph has cycles, False otherwise
        """
        logger.info("Checking for cycles in the operation dependency graph")
        logger.info(f"Graph has {len(self.nx_graph.nodes)} nodes and {len(self.nx_graph.edges)} edges")
        
        # Log the edges for debugging
        logger.info("Graph edges:")
        for edge in self.nx_graph.edges():
            logger.info(f"  {edge[0]} -> {edge[1]}")
        
        try:
            cycle = nx.find_cycle(self.nx_graph)
            logger.warning(f"Cycle detected in the graph: {cycle}")
            
            # Log the cycle path for better visualization
            cycle_path = " -> ".join([edge[0] for edge in cycle]) + " -> " + cycle[-1][1]
            logger.warning(f"Cyclic path: {cycle_path}")
            
            return True
        except nx.NetworkXNoCycle:
            logger.info("No cycles detected in the graph")
            return False
    
    def get_execution_order(self) -> List[str]:
        """
        Get a valid execution order for operations
        
        This performs a topological sort on the graph to determine an order
        in which operations can be executed, respecting dependencies.
        
        Returns:
            List of operation IDs in execution order
        
        Raises:
            NetworkXUnfeasible: If the graph has cycles and cannot be sorted
        """
        # First check for cycles - more informative error message
        if self.has_cycles():
            logger.error("Cannot determine execution order: graph has cycles")
            # Find a cycle to report in the error
            try:
                cycle = nx.find_cycle(self.nx_graph)
                cycle_path = " -> ".join([edge[0] for edge in cycle]) + " -> " + cycle[-1][1]
                logger.error(f"Cycle detected: {cycle_path}")
                raise nx.NetworkXUnfeasible(f"Graph contains a cycle: {cycle_path}")
            except nx.NetworkXNoCycle:
                # This shouldn't happen since we already checked for cycles
                pass
            except Exception as e:
                # Some other error occurred
                logger.error(f"Error finding cycle: {e}")
            
            # Generic error if we couldn't find a specific cycle
            raise nx.NetworkXUnfeasible("Cannot determine execution order: graph has cycles")
        
        try:
            # Use NetworkX topological sort
            return list(nx.topological_sort(self.nx_graph))
        except nx.NetworkXUnfeasible:
            # This should not be reached because we already checked for cycles,
            # but keep as a fallback
            logger.error("Cannot determine execution order: graph has cycles")
            raise
    
    def get_parallel_execution_plan(self) -> List[List[str]]:
        """
        Get a parallel execution plan for operations
        
        This organizes operations into layers that can be executed in parallel.
        Operations in the same layer have no dependencies between them.
        
        Returns:
            List of lists of operation IDs, where each inner list is a layer
            Empty list if the graph has cycles
        """
        if self.has_cycles():
            cycle = nx.find_cycle(self.nx_graph)
            cycle_path = " -> ".join([edge[0] for edge in cycle]) + " -> " + cycle[-1][1]
            logger.error(f"Cannot create parallel execution plan: graph has cycles. Cycle: {cycle_path}")
            return []
        
        # Keep track of operations that have all dependencies satisfied
        ready = set()
        
        # Keep track of operations that have been scheduled
        scheduled = set()
        
        # Map each operation to its remaining dependency count
        remaining_deps = {}
        for op in self.plan.operations:
            remaining_deps[op.id] = len(op.depends_on)
            if not op.depends_on:
                ready.add(op.id)
        
        # Build layers
        layers = []
        while ready:
            # Current layer is all ready operations
            layer = list(ready)
            layers.append(layer)
            
            # Mark current layer as scheduled
            scheduled.update(layer)
            
            # Find operations that become ready after this layer
            next_ready = set()
            for op_id in layer:
                # For each dependent operation
                for dep_op_id in self.graph.get(op_id, []):
                    # Decrease dependency count
                    remaining_deps[dep_op_id] -= 1
                    # If all dependencies satisfied, add to next ready set
                    if remaining_deps[dep_op_id] == 0:
                        next_ready.add(dep_op_id)
            
            # Update ready set for next iteration
            ready = next_ready
        
        # Check if all operations were scheduled
        if len(scheduled) != len(self.plan.operations):
            logger.warning(f"Not all operations scheduled: {len(scheduled)} of {len(self.plan.operations)}")
            # Log which operations weren't scheduled
            unscheduled = set(op.id for op in self.plan.operations) - scheduled
            logger.warning(f"Unscheduled operations: {unscheduled}")
        
        return layers
    
    def visualize(self, output_path: Optional[str] = None, show: bool = False) -> Optional[str]:
        """
        Generate a visualization of the DAG
        
        Args:
            output_path: Path to save the visualization (PNG, SVG, PDF)
            show: Whether to display the visualization (for interactive use)
            
        Returns:
            Base64-encoded image data (if output_path is None) or None
        """
        try:
            # Create a layout for the graph
            pos = nx.drawing.nx_agraph.graphviz_layout(self.nx_graph, prog='dot')
            
            # Create figure and axis
            plt.figure(figsize=(12, 8))
            plt.title("Operation Dependency Graph")
            
            # Draw nodes with labels
            nx.draw(
                self.nx_graph,
                pos,
                with_labels=True,
                node_color="lightblue",
                node_size=3000,
                font_size=10,
                font_weight="bold",
                arrows=True
            )
            
            # Add colored borders for different database types
            node_colors = {}
            for op in self.plan.operations:
                if hasattr(op, 'source_id'):
                    # Extract database type from source_id
                    db_type = op.source_id.split('_')[0] if '_' in op.source_id else op.source_id
                    node_colors[op.id] = db_type
            
            # Draw separate edges for operations with different source databases
            edge_colors = []
            for u, v in self.nx_graph.edges():
                source_type = node_colors.get(u, "")
                edge_colors.append(source_type)
            
            # Save or display the result
            if output_path:
                # Create the directory if it doesn't exist
                os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
                plt.savefig(output_path, bbox_inches="tight")
                logger.info(f"Saved DAG visualization to {output_path}")
                result = None
            else:
                # Return as base64 data
                buffer = BytesIO()
                plt.savefig(buffer, format="png", bbox_inches="tight")
                buffer.seek(0)
                image_data = base64.b64encode(buffer.read()).decode()
                result = image_data
            
            if show:
                plt.show()
            else:
                plt.close()
                
            return result
                
        except Exception as e:
            logger.error(f"Error visualizing DAG: {e}")
            return None
    
    def export_graphviz(self, output_path: str) -> bool:
        """
        Export the DAG to a DOT file for use with Graphviz
        
        This provides more advanced visualization options than matplotlib.
        
        Args:
            output_path: Path to save the DOT file
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Create a graphviz-focused graph
            dot_graph = nx.drawing.nx_agraph.to_agraph(self.nx_graph)
            
            # Set graph attributes
            dot_graph.graph_attr["label"] = "Operation Dependency Graph"
            dot_graph.graph_attr["labelloc"] = "t"
            dot_graph.graph_attr["fontsize"] = "20"
            
            # Set node attributes
            dot_graph.node_attr["shape"] = "box"
            dot_graph.node_attr["style"] = "filled"
            dot_graph.node_attr["fillcolor"] = "lightblue"
            
            # Set different colors for different operation types
            for op in self.plan.operations:
                node = dot_graph.get_node(op.id)
                if "postgres" in op.source_id:
                    node.attr["fillcolor"] = "lightblue"
                elif "mongodb" in op.source_id:
                    node.attr["fillcolor"] = "lightgreen"
                elif "qdrant" in op.source_id:
                    node.attr["fillcolor"] = "lightyellow"
                elif "slack" in op.source_id:
                    node.attr["fillcolor"] = "lightpink"
            
            # Save the DOT file
            dot_graph.write(output_path)
            logger.info(f"Exported DAG to DOT file: {output_path}")
            
            return True
        except Exception as e:
            logger.error(f"Error exporting DAG to DOT file: {e}")
            return False 