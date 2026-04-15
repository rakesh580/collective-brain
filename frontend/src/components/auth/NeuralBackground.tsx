import { useRef, useEffect, useCallback, useState } from "react";

/* ── Neural Network Canvas Background ── */
interface Node {
  x: number;
  y: number;
  vx: number;
  vy: number;
  radius: number;
  pulsePhase: number;
  layer: number;
}

export default function NeuralBackground() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const nodesRef = useRef<Node[]>([]);
  const mouseRef = useRef({ x: -1000, y: -1000 });
  const animRef = useRef<number>(0);

  // Check prefers-reduced-motion once on mount
  const [reducedMotion] = useState(() =>
    typeof window !== "undefined" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );

  const initNodes = useCallback((w: number, h: number) => {
    const nodes: Node[] = [];
    const count = Math.min(80, Math.floor((w * h) / 12000));
    for (let i = 0; i < count; i++) {
      nodes.push({
        x: Math.random() * w,
        y: Math.random() * h,
        vx: (Math.random() - 0.5) * 0.4,
        vy: (Math.random() - 0.5) * 0.4,
        radius: 1.5 + Math.random() * 2.5,
        pulsePhase: Math.random() * Math.PI * 2,
        layer: Math.floor(Math.random() * 3),
      });
    }
    nodesRef.current = nodes;
  }, []);

  useEffect(() => {
    // Skip the entire canvas animation when user prefers reduced motion
    if (reducedMotion) return;

    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d")!;
    let w = (canvas.width = window.innerWidth);
    let h = (canvas.height = window.innerHeight);
    initNodes(w, h);

    const colors = [
      [99, 102, 241],   // indigo-500
      [139, 92, 246],   // violet-500
      [79, 70, 229],    // indigo-600
      [167, 139, 250],  // violet-400
    ];

    const handleResize = () => {
      w = canvas.width = window.innerWidth;
      h = canvas.height = window.innerHeight;
      initNodes(w, h);
    };
    const handleMouse = (e: MouseEvent) => {
      mouseRef.current = { x: e.clientX, y: e.clientY };
    };

    window.addEventListener("resize", handleResize);
    window.addEventListener("mousemove", handleMouse);

    // Spatial grid for O(n) neighbour lookups instead of O(n²)
    const CELL_SIZE = 160; // matches maxDist for connections
    let gridCols = 0;
    let gridRows = 0;
    let grid: Int32Array; // flat array: each cell stores up to a fixed number of node indices
    const MAX_PER_CELL = 16;

    function rebuildGrid(nodes: Node[]) {
      gridCols = Math.ceil(w / CELL_SIZE) || 1;
      gridRows = Math.ceil(h / CELL_SIZE) || 1;
      const totalCells = gridCols * gridRows;
      // Layout: for each cell, first slot is count, then MAX_PER_CELL index slots
      const stride = MAX_PER_CELL + 1;
      if (!grid || grid.length < totalCells * stride) {
        grid = new Int32Array(totalCells * stride);
      }
      // Zero out counts
      for (let c = 0; c < totalCells; c++) {
        grid[c * stride] = 0;
      }
      for (let i = 0; i < nodes.length; i++) {
        const col = Math.min(Math.floor(nodes[i].x / CELL_SIZE), gridCols - 1);
        const row = Math.min(Math.floor(nodes[i].y / CELL_SIZE), gridRows - 1);
        const cellIdx = (row * gridCols + col) * stride;
        const cnt = grid[cellIdx];
        if (cnt < MAX_PER_CELL) {
          grid[cellIdx + 1 + cnt] = i;
          grid[cellIdx]++;
        }
      }
    }

    let time = 0;
    const animate = () => {
      time += 0.008;
      ctx.clearRect(0, 0, w, h);

      const nodes = nodesRef.current;
      const mouse = mouseRef.current;

      // Update positions
      for (const n of nodes) {
        n.x += n.vx;
        n.y += n.vy;
        if (n.x < 0 || n.x > w) n.vx *= -1;
        if (n.y < 0 || n.y > h) n.vy *= -1;

        // Mouse repulsion
        const dx = n.x - mouse.x;
        const dy = n.y - mouse.y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < 150) {
          const force = (150 - dist) / 150 * 0.02;
          n.vx += dx * force * 0.1;
          n.vy += dy * force * 0.1;
        }

        // Dampen velocity
        n.vx *= 0.999;
        n.vy *= 0.999;
      }

      // Rebuild spatial grid each frame
      rebuildGrid(nodes);
      const stride = MAX_PER_CELL + 1;
      const maxDistSq = CELL_SIZE * CELL_SIZE; // 160² = 25600

      // Draw connections using spatial grid (check only neighbouring cells)
      for (let i = 0; i < nodes.length; i++) {
        const a = nodes[i];
        const col = Math.min(Math.floor(a.x / CELL_SIZE), gridCols - 1);
        const row = Math.min(Math.floor(a.y / CELL_SIZE), gridRows - 1);

        // Check 3x3 neighbourhood
        for (let dr = -1; dr <= 1; dr++) {
          const nr = row + dr;
          if (nr < 0 || nr >= gridRows) continue;
          for (let dc = -1; dc <= 1; dc++) {
            const nc = col + dc;
            if (nc < 0 || nc >= gridCols) continue;
            const cellIdx = (nr * gridCols + nc) * stride;
            const cnt = grid[cellIdx];
            for (let k = 0; k < cnt; k++) {
              const j = grid[cellIdx + 1 + k];
              if (j <= i) continue; // avoid duplicate pairs
              const b = nodes[j];
              const dx = a.x - b.x;
              const dy = a.y - b.y;
              const distSq = dx * dx + dy * dy;
              if (distSq < maxDistSq) {
                const dist = Math.sqrt(distSq);
                const alpha = (1 - dist / CELL_SIZE) * 0.15;
                const pulse = Math.sin(time * 2 + a.pulsePhase) * 0.5 + 0.5;
                const c = colors[(a.layer + b.layer) % colors.length];
                ctx.beginPath();
                ctx.moveTo(a.x, a.y);
                ctx.lineTo(b.x, b.y);
                ctx.strokeStyle = `rgba(${c[0]},${c[1]},${c[2]},${alpha * (0.5 + pulse * 0.5)})`;
                ctx.lineWidth = 0.5 + pulse * 0.5;
                ctx.stroke();
              }
            }
          }
        }
      }

      // Draw nodes
      for (const n of nodes) {
        const pulse = Math.sin(time * 3 + n.pulsePhase) * 0.5 + 0.5;
        const c = colors[n.layer % colors.length];
        const r = n.radius * (0.8 + pulse * 0.4);

        // Glow
        const grad = ctx.createRadialGradient(n.x, n.y, 0, n.x, n.y, r * 4);
        grad.addColorStop(0, `rgba(${c[0]},${c[1]},${c[2]},${0.3 * pulse})`);
        grad.addColorStop(1, `rgba(${c[0]},${c[1]},${c[2]},0)`);
        ctx.beginPath();
        ctx.arc(n.x, n.y, r * 4, 0, Math.PI * 2);
        ctx.fillStyle = grad;
        ctx.fill();

        // Core
        ctx.beginPath();
        ctx.arc(n.x, n.y, r, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${c[0]},${c[1]},${c[2]},${0.6 + pulse * 0.4})`;
        ctx.fill();
      }

      // Data stream particles - find nearest via spatial grid instead of sorting
      for (let i = 0; i < 3; i++) {
        const idx = Math.floor(Math.random() * nodes.length);
        const n = nodes[idx];
        const streamT = (time * 5 + idx) % 1;

        // Find nearest node using spatial grid
        let nearestDist = Infinity;
        let nearest: Node | null = null;
        const col = Math.min(Math.floor(n.x / CELL_SIZE), gridCols - 1);
        const row = Math.min(Math.floor(n.y / CELL_SIZE), gridRows - 1);
        for (let dr = -1; dr <= 1; dr++) {
          const nr = row + dr;
          if (nr < 0 || nr >= gridRows) continue;
          for (let dc = -1; dc <= 1; dc++) {
            const nc = col + dc;
            if (nc < 0 || nc >= gridCols) continue;
            const cellIdx = (nr * gridCols + nc) * stride;
            const cnt = grid[cellIdx];
            for (let k = 0; k < cnt; k++) {
              const j = grid[cellIdx + 1 + k];
              if (j === idx) continue;
              const candidate = nodes[j];
              const d = Math.hypot(candidate.x - n.x, candidate.y - n.y);
              if (d < nearestDist) {
                nearestDist = d;
                nearest = candidate;
              }
            }
          }
        }

        if (nearest && nearestDist < 160) {
          const sx = n.x + (nearest.x - n.x) * streamT;
          const sy = n.y + (nearest.y - n.y) * streamT;
          ctx.beginPath();
          ctx.arc(sx, sy, 1, 0, Math.PI * 2);
          ctx.fillStyle = `rgba(167,139,250,${0.6 * (1 - streamT)})`;
          ctx.fill();
        }
      }

      animRef.current = requestAnimationFrame(animate);
    };

    animRef.current = requestAnimationFrame(animate);

    return () => {
      cancelAnimationFrame(animRef.current);
      window.removeEventListener("resize", handleResize);
      window.removeEventListener("mousemove", handleMouse);
    };
  }, [initNodes]);

  // When reduced motion is preferred, render a static gradient background only
  if (reducedMotion) {
    return (
      <div
        className="fixed inset-0 z-0"
        style={{ background: "linear-gradient(135deg, #0f0a1a 0%, #1a1035 30%, #0d1117 60%, #130f20 100%)" }}
      />
    );
  }

  return (
    <canvas
      ref={canvasRef}
      className="fixed inset-0 z-0"
      style={{ background: "linear-gradient(135deg, #0f0a1a 0%, #1a1035 30%, #0d1117 60%, #130f20 100%)" }}
    />
  );
}
