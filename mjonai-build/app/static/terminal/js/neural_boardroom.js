// Interactive Canvas-based Neural Consensus Synapse Graph for the AI Boardroom
function initNeuralSynapseGraph() {
  const canvas = document.getElementById('neural-synapse-canvas');
  if (!canvas) return;

  const ctx = canvas.getContext('2d');
  const dpr = window.devicePixelRatio || 1;
  canvas.width = canvas.clientWidth * dpr;
  canvas.height = canvas.clientHeight * dpr;
  ctx.scale(dpr, dpr);

  const width = canvas.clientWidth;
  const height = canvas.clientHeight;

  // Nodes: Bull, Bear, Economist, Devil, and Central Supervisor
  const nodes = [
    { id: 'supervisor', label: 'SUPERVISOR', x: width * 0.5, y: height * 0.5, color: '#00f0ff', radius: 18, isCenter: true },
    { id: 'bull', label: 'BULL', x: width * 0.2, y: height * 0.25, color: '#05ffa1', radius: 14 },
    { id: 'bear', label: 'BEAR', x: width * 0.8, y: height * 0.25, color: '#ffb800', radius: 14 },
    { id: 'economist', label: 'ECONOMIST', x: width * 0.2, y: height * 0.75, color: '#38bdf8', radius: 14 },
    { id: 'devil', label: 'DEVIL (VETO)', x: width * 0.8, y: height * 0.75, color: '#ff2a5f', radius: 15 },
  ];

  // Synaptic connections between specialists and supervisor
  const edges = [
    { from: 1, to: 0, color: '#05ffa1', active: true },
    { from: 2, to: 0, color: '#ffb800', active: true },
    { from: 3, to: 0, color: '#38bdf8', active: true },
    { from: 4, to: 0, color: '#ff2a5f', active: true },
  ];

  // Animated synaptic pulses
  const pulses = [
    { edge: 0, progress: 0.1, speed: 0.015 },
    { edge: 2, progress: 0.6, speed: 0.012 },
    { edge: 3, progress: 0.8, speed: 0.02 },
  ];

  function draw() {
    ctx.clearRect(0, 0, width, height);

    // 1. Draw Synaptic Edges
    edges.forEach((edge) => {
      const p1 = nodes[edge.from];
      const p2 = nodes[edge.to];

      ctx.beginPath();
      ctx.moveTo(p1.x, p1.y);
      ctx.lineTo(p2.x, p2.y);
      ctx.strokeStyle = edge.color + '44';
      ctx.lineWidth = 2;
      ctx.stroke();
    });

    // 2. Draw Moving Electrical Pulses
    pulses.forEach((p) => {
      p.progress += p.speed;
      if (p.progress > 1) p.progress = 0;

      const edge = edges[p.edge];
      const p1 = nodes[edge.from];
      const p2 = nodes[edge.to];

      const curX = p1.x + (p2.x - p1.x) * p.progress;
      const curY = p1.y + (p2.y - p1.y) * p.progress;

      ctx.beginPath();
      ctx.arc(curX, curY, 4, 0, Math.PI * 2);
      ctx.fillStyle = edge.color;
      ctx.shadowColor = edge.color;
      ctx.shadowBlur = 10;
      ctx.fill();
      ctx.shadowBlur = 0;
    });

    // 3. Draw Specialist Nodes
    nodes.forEach((node) => {
      // Glow ring
      ctx.beginPath();
      ctx.arc(node.x, node.y, node.radius + 3, 0, Math.PI * 2);
      ctx.strokeStyle = node.color + '66';
      ctx.lineWidth = 1.5;
      ctx.stroke();

      // Inner solid node
      ctx.beginPath();
      ctx.arc(node.x, node.y, node.radius, 0, Math.PI * 2);
      ctx.fillStyle = '#0f172a';
      ctx.fill();
      ctx.strokeStyle = node.color;
      ctx.lineWidth = 2;
      ctx.shadowColor = node.color;
      ctx.shadowBlur = 8;
      ctx.stroke();
      ctx.shadowBlur = 0;

      // Label
      ctx.fillStyle = '#f8fafc';
      ctx.font = '10px "JetBrains Mono", monospace';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(node.label, node.x, node.y + node.radius + 12);
    });

    requestAnimationFrame(draw);
  }

  draw();
}

document.addEventListener('DOMContentLoaded', initNeuralSynapseGraph);
