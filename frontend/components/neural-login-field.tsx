"use client";

import { useEffect, useRef } from "react";

export function NeuralLoginField() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    let mounted = true;
    let frame = 0;
    let cleanup = () => {};

    async function boot() {
      const canvas = canvasRef.current;
      if (!canvas || !mounted) return;

      const THREE = await import("three");
      if (!mounted) return;

      const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      const scene = new THREE.Scene();
      scene.fog = new THREE.FogExp2(0x020403, 0.014);

      const camera = new THREE.PerspectiveCamera(55, 1, 0.1, 140);
      camera.position.set(0, 0, 32);

      const renderer = new THREE.WebGLRenderer({
        canvas,
        antialias: true,
        alpha: true,
        powerPreference: "high-performance"
      });
      renderer.setClearColor(0x000000, 0);
      renderer.toneMapping = THREE.ACESFilmicToneMapping;
      renderer.toneMappingExposure = 1.25;

      const pointer = new THREE.Vector2(0, 0);
      const easedPointer = new THREE.Vector2(0, 0);
      const clock = new THREE.Clock();

      const isSmall = window.innerWidth < 720;
      const particleCount = isSmall ? 1500 : 3600;
      const positions = new Float32Array(particleCount * 3);
      const phases = new Float32Array(particleCount);
      const sizes = new Float32Array(particleCount);
      const layerCount = 7;
      const columnCount = isSmall ? 44 : 76;
      const rowCount = isSmall ? 34 : 42;

      for (let i = 0; i < particleCount; i += 1) {
        const layer = i % layerCount;
        const col = Math.floor(Math.random() * columnCount);
        const row = Math.floor(Math.random() * rowCount);
        const gridX = (col - columnCount / 2) * (isSmall ? 0.72 : 0.82);
        const gridY = (row - rowCount / 2) * (isSmall ? 0.6 : 0.64);
        const scatter = layer * 0.05;

        positions[i * 3] = gridX + (Math.random() - 0.5) * (0.18 + scatter);
        positions[i * 3 + 1] = gridY + (Math.random() - 0.5) * 0.18;
        positions[i * 3 + 2] = -42 + layer * 10.5 + (Math.random() - 0.5) * 4.2;
        phases[i] = Math.random() * Math.PI * 2;
        sizes[i] = 1.35 + Math.random() * 1.5;
      }

      const geometry = new THREE.BufferGeometry();
      geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
      geometry.setAttribute("aPhase", new THREE.BufferAttribute(phases, 1));
      geometry.setAttribute("aSize", new THREE.BufferAttribute(sizes, 1));

      const uniforms = {
        uTime: { value: 0 },
        uPointer: { value: easedPointer },
        uPixelRatio: { value: 1 }
      };

      const material = new THREE.ShaderMaterial({
        uniforms,
        transparent: true,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
        vertexShader: `
          attribute float aPhase;
          attribute float aSize;
          varying float vFade;
          varying float vPulse;
          uniform float uTime;
          uniform vec2 uPointer;
          uniform float uPixelRatio;

          mat2 rotate2d(float angle) {
            float s = sin(angle);
            float c = cos(angle);
            return mat2(c, -s, s, c);
          }

          void main() {
            vec3 p = position;
            float breath = sin(uTime * 0.72 + aPhase) * 0.62;
            float orbital = sin(uTime * 0.19 + p.z * 0.035) * 0.095;

            p.xy = rotate2d(orbital) * p.xy;
            p.x += uPointer.x * (1.2 + (p.z + 34.0) * 0.018);
            p.y += uPointer.y * (0.85 + (p.z + 34.0) * 0.014);
            p.z += breath;

            vec4 mvPosition = modelViewMatrix * vec4(p, 1.0);
            gl_Position = projectionMatrix * mvPosition;

            float depthFade = smoothstep(-48.0, 18.0, p.z);
            vFade = 0.24 + depthFade * 0.86;
            vPulse = 0.62 + sin(uTime * 1.15 + aPhase) * 0.42;
            gl_PointSize = clamp(aSize * uPixelRatio * (178.0 / -mvPosition.z), 1.65, 8.5);
          }
        `,
        fragmentShader: `
          varying float vFade;
          varying float vPulse;

          void main() {
            vec2 uv = gl_PointCoord - vec2(0.5);
            float d = length(uv);
            float dotMask = smoothstep(0.46, 0.26, d);
            vec3 accent = vec3(0.9608, 0.3059, 0.0);
            vec3 violet = vec3(0.32, 0.28, 0.78);
            vec3 color = mix(violet, accent, vFade);
            float alpha = dotMask * vFade * vPulse * 0.92;
            gl_FragColor = vec4(color, alpha);
          }
        `
      });

      const points = new THREE.Points(geometry, material);
      points.position.x = isSmall ? -2.5 : -4.5;
      points.position.y = isSmall ? 1.5 : 0;
      scene.add(points);

      const grid = new THREE.GridHelper(70, 42, 0x4b4ba0, 0x3d1808);
      grid.position.set(isSmall ? -4 : -9, -14, -9);
      grid.rotation.x = Math.PI * 0.51;
      const gridMaterial = grid.material as THREE.Material;
      gridMaterial.transparent = true;
      gridMaterial.opacity = 0.16;
      scene.add(grid);

      function resize() {
        const width = window.innerWidth;
        const height = window.innerHeight;
        const dpr = Math.min(window.devicePixelRatio || 1, 1.75);
        renderer.setPixelRatio(dpr);
        renderer.setSize(width, height, false);
        uniforms.uPixelRatio.value = dpr;
        camera.aspect = width / height;
        camera.updateProjectionMatrix();
      }

      function onPointerMove(event: PointerEvent) {
        pointer.x = (event.clientX / window.innerWidth - 0.5) * 2;
        pointer.y = -(event.clientY / window.innerHeight - 0.5) * 2;
      }

      function render() {
        const elapsed = clock.getElapsedTime();
        easedPointer.lerp(pointer, 0.035);
        uniforms.uTime.value = elapsed;

        points.rotation.y = Math.sin(elapsed * 0.12) * 0.055;
        points.rotation.x = Math.cos(elapsed * 0.1) * 0.035;
        grid.position.z = -9 + Math.sin(elapsed * 0.35) * 0.42;

        renderer.render(scene, camera);
        if (!reducedMotion) frame = window.requestAnimationFrame(render);
      }

      resize();
      render();
      window.addEventListener("resize", resize);
      window.addEventListener("pointermove", onPointerMove, { passive: true });

      cleanup = () => {
        window.removeEventListener("resize", resize);
        window.removeEventListener("pointermove", onPointerMove);
        window.cancelAnimationFrame(frame);
        geometry.dispose();
        material.dispose();
        grid.geometry.dispose();
        gridMaterial.dispose();
        renderer.dispose();
      };
    }

    void boot();

    return () => {
      mounted = false;
      cleanup();
    };
  }, []);

  return (
    <>
      <canvas
        ref={canvasRef}
        aria-hidden="true"
        className="absolute inset-0 h-full w-full opacity-100 mix-blend-screen"
      />
      <div
        aria-hidden="true"
        className="absolute inset-0 bg-[linear-gradient(115deg,rgba(75,75,160,0.26),transparent_34%),linear-gradient(90deg,rgba(0,0,0,0.15),rgba(0,0,0,0.82)_70%),linear-gradient(180deg,rgba(0,0,0,0.1),rgba(0,0,0,0.86))]"
      />
      <div
        aria-hidden="true"
        className="absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.045)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.035)_1px,transparent_1px)] bg-[size:48px_48px] opacity-35"
      />
      <div
        aria-hidden="true"
        className="absolute inset-0 opacity-[0.06] [background-image:repeating-linear-gradient(0deg,#fff_0,#fff_1px,transparent_1px,transparent_4px)]"
      />
    </>
  );
}
