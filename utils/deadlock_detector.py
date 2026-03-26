"""
utils/deadlock_detector.py
==========================
Phát hiện deadlock bằng DFS Cycle Detection trên wait-for graph.
Thuật toán: DFS với rec_stack để tìm back-edge (chu trình).
Thuộc tính kiểm chứng: AG(¬S6) — tại mọi trạng thái reachable, không tồn tại deadlock.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class DeadlockDetector:
    """
    Phát hiện circular wait trong wait-for graph bằng DFS.

    Wait-for graph:
        Node  = session/process ID
        Edge  = A → B nghĩa là "A đang chờ B release resource"
    Deadlock = tồn tại chu trình trong graph (A→B→A hoặc A→B→C→A)
    """

    def detect_cycle(
        self, graph: dict[str, list[str]]
    ) -> tuple[bool, list[str]]:
        """
        Phát hiện chu trình trong wait-for graph.

        Args:
            graph: {node: [list of nodes this node is waiting for]}

        Returns:
            (True, cycle_path)  nếu có deadlock
            (False, [])         nếu không có deadlock
        """
        visited: set[str] = set()
        rec_stack: set[str] = set()
        parent: dict[str, Optional[str]] = {node: None for node in graph}
        cycle_path: list[str] = []

        def dfs(node: str) -> bool:
            visited.add(node)
            rec_stack.add(node)

            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    parent[neighbor] = node
                    if dfs(neighbor):
                        return True
                elif neighbor in rec_stack:
                    # Tìm thấy back-edge → có chu trình
                    cycle_path.extend(self._reconstruct_cycle(parent, node, neighbor))
                    return True

            rec_stack.discard(node)
            return False

        for node in graph:
            if node not in visited:
                if dfs(node):
                    logger.warning(f"Deadlock detected! Cycle: {' → '.join(cycle_path)}")
                    return True, cycle_path

        return False, []

    def _reconstruct_cycle(
        self,
        parent: dict[str, Optional[str]],
        start: str,
        end: str,
    ) -> list[str]:
        """Tái tạo đường đi của chu trình từ back-edge."""
        path = [end, start]
        current = start
        while parent.get(current) and parent[current] != end:
            current = parent[current]
            path.append(current)
        path.append(end)
        path.reverse()
        return path

    def check_state_reachability(
        self,
        fsm_graph: dict[str, list[str]],
        target_state: str = "deadlock",
    ) -> tuple[bool, list[list[str]]]:
        """
        Kiểm tra thuộc tính AG(¬deadlock):
        Tìm tất cả đường dẫn từ 'guest' có thể đạt tới target_state.

        Returns:
            (reachable, all_paths_to_target)
        """
        all_paths: list[list[str]] = []
        self._dfs_paths(fsm_graph, "guest", target_state, [], all_paths, set())
        return len(all_paths) > 0, all_paths

    def _dfs_paths(
        self,
        graph: dict[str, list[str]],
        current: str,
        target: str,
        path: list[str],
        all_paths: list[list[str]],
        visited: set[str],
    ):
        visited.add(current)
        path = path + [current]

        if current == target:
            all_paths.append(path)
        else:
            for neighbor in graph.get(current, []):
                if neighbor not in visited:
                    self._dfs_paths(graph, neighbor, target, path, all_paths, visited.copy())

    def generate_counterexample(
        self,
        tc_id: str,
        init_state: str,
        path_taken: list[str],
        deadlock_state: str,
        reason: str,
    ) -> dict:
        """
        Sinh Counterexample Report khi phát hiện violation AG(¬S6).
        """
        return {
            "tc_id": tc_id,
            "property": "AG(¬deadlock)",
            "verdict": "VIOLATED",
            "init_state": init_state,
            "path_taken": " → ".join(path_taken),
            "deadlock_at": deadlock_state,
            "reason": reason,
            "counterexample": True,
        }
