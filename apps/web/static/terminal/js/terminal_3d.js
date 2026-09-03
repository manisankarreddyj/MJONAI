// Three.js 3D Volumetric Liquidity Dome, Gravitational Funnel & Particle Order Flow Lidar
let scene, camera, renderer, domeMesh, funnelMesh, lidarParticles;
let currentMode = "TOPOLOGY"; // "TOPOLOGY" or "DOME"

function init3DSpace() {
  const container = document.getElementById('canvas-3d-container');
  if (!container || typeof THREE === 'undefined') return;

  scene = new THREE.Scene();
  scene.fog = new THREE.FogExp2(0x030712, 0.02);

  camera = new THREE.PerspectiveCamera(50, container.clientWidth / container.clientHeight, 0.1, 1000);
  camera.position.set(0, 22, 38);
  camera.lookAt(0, 0, 0);

  renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setSize(container.clientWidth, container.clientHeight);
  renderer.setPixelRatio(window.devicePixelRatio);
  container.appendChild(renderer.domElement);

  // 1. Grid Floor Plane
  const grid = new THREE.GridHelper(60, 60, 0x00f0ff, 0x1e293b);
  grid.position.y = -0.5;
  scene.add(grid);

  // 2. Volumetric Liquidity Dome (Wireframe Geodesic Hemisphere)
  const domeGeo = new THREE.SphereGeometry(18, 32, 16, 0, Math.PI * 2, 0, Math.PI * 0.5);
  const domeMat = new THREE.MeshBasicMaterial({
    color: 0x00f0ff,
    wireframe: true,
    transparent: true,
    opacity: 0.25,
  });
  domeMesh = new THREE.Mesh(domeGeo, domeMat);
  scene.add(domeMesh);

  // 3. Central Gravitational Liquidity Funnel
  const funnelGeo = new THREE.CylinderGeometry(1, 10, 8, 32, 8, true);
  const funnelMat = new THREE.MeshBasicMaterial({
    color: 0xffb800,
    wireframe: true,
    transparent: true,
    opacity: 0.35,
  });
  funnelMesh = new THREE.Mesh(funnelGeo, funnelMat);
  funnelMesh.position.y = 3.5;
  funnelMesh.rotation.x = Math.PI;
  scene.add(funnelMesh);

  // 4. Particle Order Flow Lidar (Block Orders hitting the tape)
  const particleCount = 600;
  const particleGeo = new THREE.BufferGeometry();
  const positions = new Float32Array(particleCount * 3);
  const colors = new Float32Array(particleCount * 3);

  for (let i = 0; i < particleCount; i++) {
    const angle = Math.random() * Math.PI * 2;
    const radius = 2 + Math.random() * 20;
    const y = Math.random() * 12;

    positions[i * 3] = Math.cos(angle) * radius;
    positions[i * 3 + 1] = y;
    positions[i * 3 + 2] = Math.sin(angle) * radius;

    // Green for buy flow, red for sell flow
    const isBuy = Math.random() > 0.4;
    colors[i * 3] = isBuy ? 0.02 : 1.0;
    colors[i * 3 + 1] = isBuy ? 1.0 : 0.16;
    colors[i * 3 + 2] = isBuy ? 0.63 : 0.37;
  }

  particleGeo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  particleGeo.setAttribute('color', new THREE.BufferAttribute(colors, 3));

  const particleMat = new THREE.PointsMaterial({
    size: 0.6,
    vertexColors: true,
    transparent: true,
    opacity: 0.85,
    blending: THREE.AdditiveBlending,
  });

  lidarParticles = new THREE.Points(particleGeo, particleMat);
  scene.add(lidarParticles);

  // 5. Stock Nodes Pillars (NIFTY 100 universe)
  const symbols = ['RELIANCE', 'INFY', 'TCS', 'HDFCBANK', 'ICICIBANK', 'SBIN', 'LT', 'BHARTIARTL', 'TATAMOTORS', 'ITC'];
  const nodeGeo = new THREE.BoxGeometry(1.6, 1, 1.6);
  const nodes = [];

  symbols.forEach((sym, idx) => {
    const angle = (idx / symbols.length) * Math.PI * 2;
    const dist = 12;
    const x = Math.cos(angle) * dist;
    const z = Math.sin(angle) * dist;
    const height = 3 + Math.random() * 7;
    const isGreen = Math.random() > 0.3;

    const mat = new THREE.MeshBasicMaterial({
      color: isGreen ? 0x05ffa1 : 0xff2a5f,
      wireframe: true,
    });

    const mesh = new THREE.Mesh(nodeGeo, mat);
    mesh.scale.set(1, height, 1);
    mesh.position.set(x, height / 2, z);
    scene.add(mesh);
    nodes.push(mesh);
  });

  // Animation Loop
  let clock = 0;
  function animate() {
    requestAnimationFrame(animate);
    clock += 0.01;

    // Rotate dome & funnel
    domeMesh.rotation.y += 0.001;
    funnelMesh.rotation.y -= 0.003;
    grid.rotation.y += 0.0004;

    // Pulse dome opacity based on volatility
    domeMesh.material.opacity = 0.2 + Math.sin(clock * 2) * 0.08;

    // Animate Lidar particles swirling into the center
    const pos = lidarParticles.geometry.attributes.position.array;
    for (let i = 0; i < particleCount; i++) {
      pos[i * 3 + 1] -= 0.05;
      if (pos[i * 3 + 1] < 0) {
        pos[i * 3 + 1] = 12;
      }
    }
    lidarParticles.geometry.attributes.position.needsUpdate = true;
    lidarParticles.rotation.y += 0.002;

    renderer.render(scene, camera);
  }
  animate();

  window.addEventListener('resize', () => {
    if (!container || !renderer || !camera) return;
    camera.aspect = container.clientWidth / container.clientHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(container.clientWidth, container.clientHeight);
  });
}

document.addEventListener('DOMContentLoaded', init3DSpace);
