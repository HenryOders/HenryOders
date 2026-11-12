/* Weltraum-Müllabfuhr · Prototyp
   Einzelspieler: Schrott im Orbit einsammeln, Sicherungsseil, Greifhaken, Schleuse,
   Luft und Treibstoff, Kettenreaktion bei zerlegten Satelliten, Schichten und Werkstatt. */
(function () {
  'use strict';
  const T = window.THREE;

  // ===================== Hilfsfunktionen =====================
  const $ = id => document.getElementById(id);
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  const glatt = (a, b, x) => { const t = clamp((x - a) / (b - a), 0, 1); return t * t * (3 - 2 * t); };
  const V = (x = 0, y = 0, z = 0) => new T.Vector3(x, y, z);
  const geld = n => Math.round(n).toLocaleString('de-DE') + ' €';
  const zeitText = s => { s = Math.max(0, Math.ceil(s)); return Math.floor(s / 60) + ':' + String(s % 60).padStart(2, '0'); };
  function zufallsQuelle(seed) {
    let s = (seed >>> 0) || 1;
    return () => { s ^= s << 13; s >>>= 0; s ^= s >>> 17; s ^= s << 5; s >>>= 0; return s / 4294967296; };
  }
  function zufallsRichtung(r) {
    const u = r() * 2 - 1, w = r() * Math.PI * 2, s = Math.sqrt(1 - u * u);
    return V(s * Math.cos(w), u, s * Math.sin(w));
  }
  const _a = V(), _b = V(), _c = V(), _d = V();
  const OBEN = V(0, 1, 0), UNTEN = V(0, -1, 0), Z_ACHSE = V(0, 0, 1);

  // ===================== Spielstand =====================
  const SPEICHER = 'weltraum-muellabfuhr-v1';
  const UPGRADES = [
    { key: 'tank', name: 'Sauerstofftank', text: '+60 Sekunden Luft', preise: [150, 300, 500, 800] },
    { key: 'duese', name: 'Treibstofftank', text: '+40 % Treibstoff', preise: [120, 240, 400] },
    { key: 'seil', name: 'Sicherungsseil', text: '+15 m Seillänge', preise: [100, 220, 380] },
    { key: 'haken', name: 'Greifhaken', text: '+12 m Reichweite, schneller einholen', preise: [150, 320, 520] },
    { key: 'magnet', name: 'Schleusen-Magnet', text: 'zieht Schrott in der Nähe in die Schleuse', preise: [250, 450, 700] },
    { key: 'lampe', name: 'Helmlampe', text: 'heller und weiter', preise: [80, 180] },
  ];
  const standardStand = () => ({ credits: 0, schicht: 1, upgrades: {}, alterAnzug: false, rekord: 0, verwarnungen: 0 });
  function laden() {
    try {
      const s = JSON.parse(localStorage.getItem(SPEICHER));
      if (s && typeof s === 'object') return Object.assign(standardStand(), s, { upgrades: Object.assign({}, s.upgrades || {}) });
    } catch (e) { /* kein Speicher verfügbar */ }
    return standardStand();
  }
  let stand = laden();
  function speichern() { try { localStorage.setItem(SPEICHER, JSON.stringify(stand)); } catch (e) { /* egal */ } }
  const stufe = k => stand.upgrades[k] || 0;
  function werte() {
    return {
      luft: 240 + 60 * stufe('tank'),
      sprit: 100 * (1 + 0.4 * stufe('duese')),
      seil: 35 + 15 * stufe('seil'),
      reichweite: 45 + 12 * stufe('haken'),
      einholen: 5 + 2 * stufe('haken'),
      magnet: [0, 9, 15, 22][stufe('magnet')],
    };
  }
  const SCHICHT_DAUER = 420;
  const zielFuer = nr => 250 + 150 * (nr - 1);
  const TRAGKRAFT = 25;

  // ===================== Grafik-Grundlagen =====================
  const leinwand = $('welt');
  let renderer;
  try {
    renderer = new T.WebGLRenderer({ canvas: leinwand, antialias: true });
  } catch (e) {
    $('start-knopf').textContent = 'WebGL fehlt';
    document.querySelector('#startbild .karte p').textContent = 'Dein Browser kann leider kein WebGL. Probier Chrome, Edge oder Firefox.';
    return;
  }
  renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1));
  const szene = new T.Scene();
  szene.background = new T.Color(0x000004);
  const kamera = new T.PerspectiveCamera(72, 1, 0.05, 40000);
  szene.add(kamera);
  function groesse() {
    const w = window.innerWidth, h = window.innerHeight;
    renderer.setSize(w, h, false);
    kamera.aspect = w / h;
    kamera.updateProjectionMatrix();
  }
  window.addEventListener('resize', groesse);
  groesse();

  const umgebung = new T.AmbientLight(0x8899bb, 0.24);
  szene.add(umgebung);
  const sonne = new T.DirectionalLight(0xfff3dd, 1.55);
  szene.add(sonne, sonne.target);
  const erdlicht = new T.DirectionalLight(0x4f86d9, 0.35);
  erdlicht.position.set(0, -1, 0);
  szene.add(erdlicht, erdlicht.target);
  const lampe = new T.SpotLight(0xe8f6ff, 1.2, 60, 0.45, 0.5, 1.1);
  const lampenZiel = new T.Object3D();
  lampenZiel.position.set(0, 0, -1);
  kamera.add(lampe, lampenZiel);
  lampe.target = lampenZiel;

  // ===================== Erde, Sterne, Sonne =====================
  const ERDE_R = 2600;
  const ERDE_MITTE = V(0, -3650, 0);
  const ERD_WINKEL = Math.asin(ERDE_R / ERDE_MITTE.length());
  const ORBIT_DAUER = 300;
  const SONNE_START = V(0.55, 0.78, 0.33).normalize();
  const sonnenRichtung = SONNE_START.clone();

  function platzhalter(farbe) {
    const c = document.createElement('canvas'); c.width = c.height = 2;
    const g = c.getContext('2d'); g.fillStyle = farbe; g.fillRect(0, 0, 2, 2);
    return new T.CanvasTexture(c);
  }
  const erdUniforms = {
    tagKarte: { value: platzhalter('#1c4f86') },
    nachtKarte: { value: platzhalter('#000000') },
    sonnenRichtung: { value: sonnenRichtung.clone() },
  };
  const erdMaterial = new T.ShaderMaterial({
    uniforms: erdUniforms,
    vertexShader: `
      varying vec2 vUv; varying vec3 vN; varying vec3 vPosW;
      void main() {
        vUv = uv;
        vN = normalize(mat3(modelMatrix) * normal);
        vec4 w = modelMatrix * vec4(position, 1.0);
        vPosW = w.xyz;
        gl_Position = projectionMatrix * viewMatrix * w;
      }`,
    fragmentShader: `
      uniform sampler2D tagKarte; uniform sampler2D nachtKarte; uniform vec3 sonnenRichtung;
      varying vec2 vUv; varying vec3 vN; varying vec3 vPosW;
      void main() {
        vec3 n = normalize(vN);
        float ndl = dot(n, sonnenRichtung);
        vec3 tag = texture2D(tagKarte, vUv).rgb;
        vec3 nacht = texture2D(nachtKarte, vUv).rgb;
        float licht = clamp(ndl * 1.15 + 0.05, 0.0, 1.0);
        vec3 farbe = tag * (0.025 + licht * 1.05);
        farbe += nacht * smoothstep(0.08, -0.22, ndl) * 1.35;
        vec3 v = normalize(cameraPosition - vPosW);
        float rand = pow(1.0 - max(dot(n, v), 0.0), 2.5);
        farbe += vec3(0.32, 0.58, 1.0) * rand * clamp(ndl + 0.25, 0.0, 1.0) * 0.85;
        gl_FragColor = vec4(farbe, 1.0);
      }`,
  });
  const erde = new T.Mesh(new T.SphereGeometry(ERDE_R, 128, 80), erdMaterial);
  erde.position.copy(ERDE_MITTE);
  szene.add(erde);
  const wolkenMaterial = new T.MeshLambertMaterial({ color: 0xffffff, transparent: true, opacity: 0, depthWrite: false });
  const wolkenKugel = new T.Mesh(new T.SphereGeometry(ERDE_R * 1.006, 128, 80), wolkenMaterial);
  erde.add(wolkenKugel);
  const atmosphaere = new T.Mesh(new T.SphereGeometry(ERDE_R * 1.04, 128, 80), new T.ShaderMaterial({
    uniforms: { sonnenRichtung: erdUniforms.sonnenRichtung },
    vertexShader: `
      varying vec3 vN; varying vec3 vPosW;
      void main() {
        vN = normalize(mat3(modelMatrix) * normal);
        vec4 w = modelMatrix * vec4(position, 1.0);
        vPosW = w.xyz;
        gl_Position = projectionMatrix * viewMatrix * w;
      }`,
    fragmentShader: `
      uniform vec3 sonnenRichtung; varying vec3 vN; varying vec3 vPosW;
      void main() {
        vec3 n = normalize(vN);
        vec3 v = normalize(cameraPosition - vPosW);
        float glanz = pow(1.0 - abs(dot(n, v)), 3.2);
        float tag = clamp(dot(n, sonnenRichtung) + 0.35, 0.0, 1.0);
        gl_FragColor = vec4(vec3(0.32, 0.62, 1.0) * glanz * tag * 1.4, 1.0);
      }`,
    blending: T.AdditiveBlending, transparent: true, depthWrite: false,
  }));
  atmosphaere.position.copy(ERDE_MITTE);
  szene.add(atmosphaere);

  // Erdkarten: Land, Meer, Eis, Stadtlichter und Wolken aus Rauschen auf der Kugel (nahtlos)
  function rauschen3(seed) {
    const r = zufallsQuelle(seed), perm = new Uint8Array(512), werteFeld = new Float32Array(256);
    for (let i = 0; i < 256; i++) { perm[i] = i; werteFeld[i] = r(); }
    for (let i = 255; i > 0; i--) { const j = Math.floor(r() * (i + 1)); const t = perm[i]; perm[i] = perm[j]; perm[j] = t; }
    for (let i = 0; i < 256; i++) perm[i + 256] = perm[i];
    const h = (x, y, z) => werteFeld[perm[perm[perm[x & 255] + (y & 255)] + (z & 255)]];
    const f = t => t * t * (3 - 2 * t);
    const l = (a, b, t) => a + (b - a) * t;
    return (x, y, z) => {
      const xi = Math.floor(x), yi = Math.floor(y), zi = Math.floor(z);
      const xf = f(x - xi), yf = f(y - yi), zf = f(z - zi);
      const a = l(l(h(xi, yi, zi), h(xi + 1, yi, zi), xf), l(h(xi, yi + 1, zi), h(xi + 1, yi + 1, zi), xf), yf);
      const b = l(l(h(xi, yi, zi + 1), h(xi + 1, yi, zi + 1), xf), l(h(xi, yi + 1, zi + 1), h(xi + 1, yi + 1, zi + 1), xf), yf);
      return l(a, b, zf);
    };
  }
  function fbm(n, x, y, z, okt) {
    let s = 0, a = 0.5, f = 1, sum = 0;
    for (let i = 0; i < okt; i++) { s += a * n(x * f, y * f, z * f); sum += a; a *= 0.5; f *= 2.03; }
    return s / sum;
  }
  async function erdKartenErzeugen(fortschritt) {
    const B = 1024, H = 512;
    const neu = () => { const c = document.createElement('canvas'); c.width = B; c.height = H; return c; };
    const tag = neu(), nacht = neu(), wolken = neu();
    const tBild = tag.getContext('2d').createImageData(B, H);
    const nBild = nacht.getContext('2d').createImageData(B, H);
    const wBild = wolken.getContext('2d').createImageData(B, H);
    const land = rauschen3(11), feucht = rauschen3(23), stadt = rauschen3(37), wolke = rauschen3(51);
    for (let y = 0; y < H; y++) {
      const breite = (0.5 - (y + 0.5) / H) * Math.PI;
      const cb = Math.cos(breite), sb = Math.sin(breite);
      const polar = Math.abs(breite) / (Math.PI / 2);
      for (let x = 0; x < B; x++) {
        const laenge = (x + 0.5) / B * Math.PI * 2;
        const px = cb * Math.cos(laenge), py = sb, pz = cb * Math.sin(laenge);
        const h = fbm(land, px * 1.7 + 5, py * 1.7 + 5, pz * 1.7 + 5, 5);
        const i = (y * B + x) * 4;
        let r, g, b;
        if (h < 0.5) {
          const t = clamp((0.5 - h) / 0.2, 0, 1);
          r = 30 - 18 * t; g = 98 - 54 * t; b = 170 - 72 * t;
        } else {
          const e = (h - 0.5) / 0.5;
          const m = fbm(feucht, px * 2.4 + 9, py * 2.4, pz * 2.4, 3);
          if (e < 0.025) { r = 198; g = 188; b = 142; }
          else if (m < 0.43 && polar < 0.55) { r = 200 - e * 60; g = 164 - e * 50; b = 106 - e * 30; }
          else { r = 72 + e * 60; g = 130 - e * 30; b = 60 + e * 10; }
          if (e > 0.42) { r = 130; g = 120; b = 106; }
          const s = fbm(stadt, px * 9, py * 9, pz * 9, 3);
          if (s > 0.6 && e < 0.4 && polar < 0.75 && m >= 0.4) {
            const k = clamp((s - 0.6) * 6, 0, 1);
            nBild.data[i] = 255 * k; nBild.data[i + 1] = 196 * k; nBild.data[i + 2] = 112 * k;
          }
        }
        if (polar > 0.82 || (polar > 0.7 && h > 0.46)) { r = 236; g = 242; b = 247; }
        tBild.data[i] = r; tBild.data[i + 1] = g; tBild.data[i + 2] = b; tBild.data[i + 3] = 255;
        nBild.data[i + 3] = 255;
        const w = fbm(wolke, px * 2.6 + 3, py * 4.2 + 1, pz * 2.6, 4);
        wBild.data[i] = wBild.data[i + 1] = wBild.data[i + 2] = 255;
        wBild.data[i + 3] = glatt(0.5, 0.68, w) * (polar > 0.9 ? 0.5 : 1) * 235;
      }
      if (y % 32 === 31) { fortschritt((y + 1) / H); await new Promise(r => setTimeout(r, 0)); }
    }
    tag.getContext('2d').putImageData(tBild, 0, 0);
    nacht.getContext('2d').putImageData(nBild, 0, 0);
    wolken.getContext('2d').putImageData(wBild, 0, 0);
    erdUniforms.tagKarte.value = new T.CanvasTexture(tag);
    erdUniforms.nachtKarte.value = new T.CanvasTexture(nacht);
    wolkenMaterial.map = new T.CanvasTexture(wolken);
    wolkenMaterial.opacity = 1;
    wolkenMaterial.needsUpdate = true;
  }

  const sternenGruppe = new T.Group();
  (function sterne() {
    const r = zufallsQuelle(7), n = 4500, pos = new Float32Array(n * 3), farbe = new Float32Array(n * 3);
    for (let i = 0; i < n; i++) {
      const d = zufallsRichtung(r).multiplyScalar(20000);
      pos[i * 3] = d.x; pos[i * 3 + 1] = d.y; pos[i * 3 + 2] = d.z;
      const h = 0.45 + r() * 0.55, t = r();
      farbe[i * 3] = h * (t < 0.15 ? 1 : 0.86); farbe[i * 3 + 1] = h * 0.92; farbe[i * 3 + 2] = h * (t > 0.85 ? 0.72 : 1);
    }
    const g = new T.BufferGeometry();
    g.setAttribute('position', new T.BufferAttribute(pos, 3));
    g.setAttribute('color', new T.BufferAttribute(farbe, 3));
    sternenGruppe.add(new T.Points(g, new T.PointsMaterial({ size: 1.7, sizeAttenuation: false, vertexColors: true, depthWrite: false })));
  })();
  szene.add(sternenGruppe);
  (function staub() {
    const r = zufallsQuelle(99), n = 900, pos = new Float32Array(n * 3);
    for (let i = 0; i < n; i++) {
      const d = zufallsRichtung(r).multiplyScalar(6 + Math.pow(r(), 0.7) * 90);
      pos[i * 3] = d.x; pos[i * 3 + 1] = d.y * 0.8; pos[i * 3 + 2] = d.z;
    }
    const g = new T.BufferGeometry();
    g.setAttribute('position', new T.BufferAttribute(pos, 3));
    szene.add(new T.Points(g, new T.PointsMaterial({ color: 0xa9b0ba, size: 0.07, sizeAttenuation: true, transparent: true, opacity: 0.75, depthWrite: false })));
  })();

  function leuchtTextur(stopps) {
    const c = document.createElement('canvas'); c.width = c.height = 256;
    const g = c.getContext('2d'), v = g.createRadialGradient(128, 128, 0, 128, 128, 128);
    stopps.forEach(([p, f]) => v.addColorStop(p, f));
    g.fillStyle = v; g.fillRect(0, 0, 256, 256);
    return new T.CanvasTexture(c);
  }
  const sonnenBild = new T.Sprite(new T.SpriteMaterial({
    map: leuchtTextur([[0, 'rgba(255,255,255,1)'], [0.06, 'rgba(255,250,230,1)'], [0.16, 'rgba(255,220,150,.45)'], [0.45, 'rgba(255,170,80,.08)'], [1, 'rgba(0,0,0,0)']]),
    blending: T.AdditiveBlending, depthWrite: false, transparent: true,
  }));
  sonnenBild.scale.set(2600, 2600, 1);
  szene.add(sonnenBild);

  let orbitZeit = 40, nacht = 0;
  function himmelAktualisieren() {
    const w = -orbitZeit / ORBIT_DAUER * Math.PI * 2;
    sonnenRichtung.copy(SONNE_START).applyAxisAngle(Z_ACHSE, w);
    erde.rotation.z = w;
    sternenGruppe.rotation.z = w;
    wolkenKugel.rotation.y = orbitZeit * 0.0035;
    erdUniforms.sonnenRichtung.value.copy(sonnenRichtung);
    nacht = glatt(ERD_WINKEL + 0.035, ERD_WINKEL - 0.035, sonnenRichtung.angleTo(UNTEN));
    sonne.position.copy(sonnenRichtung).multiplyScalar(100);
    sonne.intensity = 1.55 * (1 - nacht);
    umgebung.intensity = 0.24 - 0.15 * nacht;
    erdlicht.intensity = 0.38 * (1 - nacht) * clamp(sonnenRichtung.y * 0.6 + 0.6, 0, 1);
    lampe.intensity = (0.9 + 1.2 * nacht) * (1 + 0.35 * stufe('lampe'));
    lampe.distance = 55 + 25 * stufe('lampe');
    sonnenBild.position.copy(sonnenRichtung).multiplyScalar(16000);
  }

  // ===================== Materialien und Bauteile =====================
  function streifenTextur() {
    const c = document.createElement('canvas'); c.width = 128; c.height = 32;
    const g = c.getContext('2d');
    g.fillStyle = '#ffc61a'; g.fillRect(0, 0, 128, 32);
    g.fillStyle = '#1a1a1a';
    for (let x = -32; x < 160; x += 32) { g.beginPath(); g.moveTo(x, 32); g.lineTo(x + 16, 32); g.lineTo(x + 32, 0); g.lineTo(x + 16, 0); g.closePath(); g.fill(); }
    const t = new T.CanvasTexture(c); t.wrapS = t.wrapT = T.RepeatWrapping; t.repeat.set(3, 1);
    return t;
  }
  function schildTextur(text, farbe, groesse = 64, breite = 1024, hoehe = 128) {
    const c = document.createElement('canvas'); c.width = breite; c.height = hoehe;
    const g = c.getContext('2d');
    g.font = `800 ${groesse}px "Segoe UI", system-ui, sans-serif`;
    g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillStyle = farbe;
    g.fillText(text, breite / 2, hoehe / 2 + 4);
    return new T.CanvasTexture(c);
  }
  function paneelTextur() {
    const c = document.createElement('canvas'); c.width = 128; c.height = 64;
    const g = c.getContext('2d');
    g.fillStyle = '#1d3d86'; g.fillRect(0, 0, 128, 64);
    g.strokeStyle = '#8fb3ff'; g.lineWidth = 1.5;
    for (let x = 0; x <= 128; x += 16) { g.beginPath(); g.moveTo(x, 0); g.lineTo(x, 64); g.stroke(); }
    for (let y = 0; y <= 64; y += 16) { g.beginPath(); g.moveTo(0, y); g.lineTo(128, y); g.stroke(); }
    return new T.CanvasTexture(c);
  }
  const paneelKarte = paneelTextur();
  const MAT = {
    rumpf: new T.MeshPhongMaterial({ color: 0xe4e8ee, flatShading: true, shininess: 30 }),
    orange: new T.MeshPhongMaterial({ color: 0xff8a1f, flatShading: true, shininess: 20 }),
    dunkel: new T.MeshPhongMaterial({ color: 0x2a2f38, flatShading: true }),
    schlund: new T.MeshBasicMaterial({ color: 0x030507 }),
    metall: new T.MeshPhongMaterial({ color: 0x9aa3ad, flatShading: true, shininess: 70 }),
    paneel: new T.MeshPhongMaterial({ map: paneelKarte, emissive: 0x050d22, shininess: 90, specular: 0x99bbff }),
    streifen: new T.MeshPhongMaterial({ map: streifenTextur(), flatShading: true }),
    fenster: new T.MeshBasicMaterial({ color: 0x86d9ff }),
    gruen: new T.MeshBasicMaterial({ color: 0x5dff9b }),
    blau: new T.MeshBasicMaterial({ color: 0x59c8ff }),
    rot: new T.MeshBasicMaterial({ color: 0xff3b3b }),
    gold: new T.MeshPhongMaterial({ color: 0xd4a531, emissive: 0x241900, flatShading: true, shininess: 90, specular: 0xffe9a8 }),
    weiss: new T.MeshPhongMaterial({ color: 0xf2f2f2, flatShading: true }),
    braun: new T.MeshPhongMaterial({ color: 0x7a5534, flatShading: true }),
    rotStoff: new T.MeshPhongMaterial({ color: 0xc8352e, flatShading: true }),
    pizza: new T.MeshPhongMaterial({ color: 0xe8b04a, flatShading: true }),
    salami: new T.MeshPhongMaterial({ color: 0xb8322a, flatShading: true }),
    schwarz: new T.MeshPhongMaterial({ color: 0x15161a, flatShading: true, shininess: 80 }),
    truemmer: new T.MeshPhongMaterial({ color: 0x8d8f96, flatShading: true }),
    glut: new T.MeshPhongMaterial({ color: 0xffb066, emissive: 0xff5a00, flatShading: true }),
    hakenSeil: new T.MeshBasicMaterial({ color: 0x9fe3ff }),
    seil: new T.MeshLambertMaterial({ color: 0xff9c33, emissive: 0x221000 }),
  };
  function kasten(b, h, t, mat) { return new T.Mesh(new T.BoxGeometry(b, h, t), mat); }
  function rohr(r1, r2, h, seg, mat) { return new T.Mesh(new T.CylinderGeometry(r1, r2, h, seg), mat); }
  function setze(m, x, y, z, eltern) { m.position.set(x, y, z); if (eltern) eltern.add(m); return m; }

  // ===================== Das Müllschiff =====================
  const schiff = new T.Group();
  szene.add(schiff);
  const ANKER = V(2, 6.45, 0);
  const STATION = V(2, 6.6, 0);
  const SCHLEUSE_MIN = V(-12, -3.2, -3.2), SCHLEUSE_MAX = V(-8, 3.2, 3.2);
  const SCHLEUSE_MITTE = V(-9.6, 0, 0);
  const SCHIFF_KAESTEN = [
    [V(-8, -3.5, -4.5), V(8, 3.5, 4.5)],
    [V(8, -2.2, -2.8), V(11.5, 2.2, 2.8)],
    [V(0.2, 3.5, -1.75), V(3.8, 6.25, 1.75)],
    [V(-3.2, -0.15, 4.5), V(3.2, 0.15, 11)],
    [V(-3.2, -0.15, -11), V(3.2, 0.15, -4.5)],
  ];
  const navLichter = [];
  (function schiffBauen() {
    setze(kasten(16, 7, 9, MAT.rumpf), 0, 0, 0, schiff);
    setze(kasten(15.5, 1, 9.06, MAT.orange), 0.25, -1.7, 0, schiff);
    setze(kasten(15.5, 0.25, 9.06, MAT.dunkel), 0.25, -2.35, 0, schiff);
    // Cockpit
    setze(kasten(3.5, 4.4, 5.6, MAT.rumpf), 9.75, 0, 0, schiff);
    setze(kasten(0.06, 1.5, 4.4, MAT.fenster), 11.53, 0.7, 0, schiff);
    // Station mit Luft und Treibstoff
    setze(rohr(1.75, 1.75, 2.75, 18, MAT.rumpf), 2, 4.85, 0, schiff);
    const ring = new T.Mesh(new T.TorusGeometry(1.78, 0.12, 8, 32), MAT.blau);
    ring.rotation.x = Math.PI / 2;
    setze(ring, 2, 6.15, 0, schiff);
    const anker = new T.Mesh(new T.TorusGeometry(0.35, 0.08, 8, 16), MAT.orange);
    setze(anker, ANKER.x, ANKER.y, ANKER.z, schiff);
    const stationsSchild = new T.Mesh(new T.PlaneGeometry(3.2, 0.5), new T.MeshBasicMaterial({ map: schildTextur('LUFT + SPRIT', '#59c8ff', 70), transparent: true }));
    setze(stationsSchild, 2, 4.9, 1.77, schiff);
    const blauLicht = new T.PointLight(0x59c8ff, 0.8, 16);
    setze(blauLicht, 2, 7.5, 0, schiff);
    // Schleuse am Heck
    const schlund = new T.Mesh(new T.PlaneGeometry(5.6, 5.6), MAT.schlund);
    schlund.rotation.y = -Math.PI / 2;
    setze(schlund, -8.02, 0, 0, schiff);
    const muellSchild = new T.Mesh(new T.PlaneGeometry(4.6, 0.9), new T.MeshBasicMaterial({ map: schildTextur('MÜLL HIER REIN', '#5dff9b', 86), transparent: true }));
    muellSchild.rotation.y = -Math.PI / 2;
    setze(muellSchild, -8.04, 1.6, 0, schiff);
    setze(kasten(0.5, 0.6, 6.8, MAT.streifen), -8.1, 3.1, 0, schiff);
    setze(kasten(0.5, 0.6, 6.8, MAT.streifen), -8.1, -3.1, 0, schiff);
    setze(kasten(0.5, 5.6, 0.6, MAT.streifen), -8.1, 0, 3.1, schiff);
    setze(kasten(0.5, 5.6, 0.6, MAT.streifen), -8.1, 0, -3.1, schiff);
    for (const [b, h, y, z] of [[0.08, 0.08, 2.5, 0], [0.08, 0.08, -2.5, 0]]) setze(kasten(b, h, 5, MAT.gruen), -8.05, y, z, schiff);
    for (const z of [2.5, -2.5]) setze(kasten(0.08, 5, 0.08, MAT.gruen), -8.05, 0, z, schiff);
    const gruenLicht = new T.PointLight(0x5dff9b, 0.9, 20);
    setze(gruenLicht, -10.5, 0, 0, schiff);
    // Firmenschrift
    for (const s of [1, -1]) {
      const schrift = new T.Mesh(new T.PlaneGeometry(11, 1.4), new T.MeshBasicMaterial({ map: schildTextur('ORBIT-ENTSORGUNG GmbH', '#ff8a1f', 78), transparent: true }));
      schrift.rotation.y = s > 0 ? 0 : Math.PI;
      setze(schrift, 0, 1.4, 4.53 * s, schiff);
    }
    // Solarflügel
    for (const s of [1, -1]) {
      setze(rohr(0.15, 0.15, 3.2, 8, MAT.metall), 0, 0, 5.9 * s, schiff).rotation.x = Math.PI / 2;
      setze(kasten(6.4, 0.12, 6.4, MAT.paneel), 0, 0, 7.75 * s, schiff);
      const nav = new T.Mesh(new T.SphereGeometry(0.25, 10, 8), s > 0 ? MAT.gruen : MAT.rot);
      setze(nav, 0, 0.3, 11.05 * s, schiff);
      navLichter.push(nav);
    }
    // Antenne und Düsen
    setze(rohr(0.06, 0.06, 3, 6, MAT.metall), 5, 5, 3, schiff);
    const schuessel = new T.Mesh(new T.SphereGeometry(0.9, 16, 8, 0, Math.PI * 2, 0, Math.PI / 2.6), MAT.weiss);
    schuessel.material = new T.MeshPhongMaterial({ color: 0xf2f2f2, side: T.DoubleSide, flatShading: true });
    schuessel.rotation.x = Math.PI;
    setze(schuessel, 5, 6.8, 3, schiff);
    for (const z of [2.5, -2.5]) setze(rohr(0.7, 1.1, 1.6, 12, MAT.dunkel), 4, -4.2, z, schiff);
  })();

  // ===================== Schrott =====================
  const TYPEN = {
    schraube: { name: 'Schraube', masse: 0.3, r: 0.36, wert: 3, skala: 1.8 },
    handschuh: { name: 'Verlorener Handschuh', masse: 0.5, r: 0.46, wert: 25, skala: 1.55 },
    pizza: { name: 'Gefrorene Pizza', masse: 0.6, r: 0.52, wert: 12, skala: 1.55 },
    beutel: { name: 'Toilettenbeutel', masse: 1, r: 0.5, wert: 2, skala: 1.5 },
    tasche: { name: 'Werkzeugtasche', masse: 4, r: 0.6, wert: 45, skala: 1.4 },
    paneel: { name: 'Solarpaneel-Stück', masse: 6, r: 0.95, wert: 30 },
    tank: { name: 'Alter Treibstofftank', masse: 20, r: 0.95, wert: 60 },
    satellit: { name: 'Alter Satellit', masse: 120, r: 2.6, wert: 400, zerbrechlich: true },
    rakete: { name: 'Raketenstufe', masse: 220, r: 3.3, wert: 650 },
    geheim: { name: 'Geheim-Satellit', masse: 90, r: 2.2, wert: 1500, zerbrechlich: true },
    truemmer: { name: 'Trümmerteil', masse: 2, r: 0.32, wert: 4 },
    anzug: { name: 'Dein alter Anzug', masse: 100, r: 0.9, wert: 150 },
  };
  function schrottModell(typ, r) {
    const g = new T.Group();
    let blink = null;
    switch (typ) {
      case 'schraube': {
        setze(rohr(0.05, 0.05, 0.34, 6, MAT.metall), 0, 0, 0, g).rotation.z = Math.PI / 2;
        setze(rohr(0.11, 0.11, 0.07, 6, MAT.metall), 0.17, 0, 0, g).rotation.z = Math.PI / 2;
        break;
      }
      case 'handschuh': {
        setze(new T.Mesh(new T.SphereGeometry(0.18, 8, 6), MAT.weiss), 0, 0, 0, g).scale.set(1.2, 0.6, 1);
        for (let i = 0; i < 4; i++) setze(kasten(0.05, 0.05, 0.16, MAT.weiss), -0.12 + i * 0.08, 0, 0.2, g);
        setze(kasten(0.07, 0.06, 0.13, MAT.weiss), 0.2, 0, 0.05, g).rotation.y = -0.6;
        setze(rohr(0.16, 0.16, 0.12, 8, MAT.orange), 0, 0, -0.18, g).rotation.x = Math.PI / 2;
        break;
      }
      case 'pizza': {
        setze(rohr(0.32, 0.32, 0.04, 14, MAT.pizza), 0, 0, 0, g);
        for (let i = 0; i < 6; i++) { const w = i / 6 * Math.PI * 2; setze(rohr(0.06, 0.06, 0.05, 8, MAT.salami), Math.cos(w) * 0.17, 0.01, Math.sin(w) * 0.17, g); }
        break;
      }
      case 'beutel': {
        setze(new T.Mesh(new T.IcosahedronGeometry(0.3, 1), MAT.braun), 0, 0, 0, g).scale.set(1, 0.85, 0.9);
        setze(rohr(0.05, 0.08, 0.12, 6, MAT.braun), 0, 0.3, 0, g);
        break;
      }
      case 'tasche': {
        setze(kasten(0.62, 0.36, 0.32, MAT.rotStoff), 0, 0, 0, g);
        setze(kasten(0.64, 0.06, 0.34, MAT.weiss), 0, 0.05, 0, g);
        setze(new T.Mesh(new T.TorusGeometry(0.12, 0.025, 6, 12, Math.PI), MAT.dunkel), 0, 0.18, 0, g);
        break;
      }
      case 'paneel': {
        setze(kasten(1.7, 0.06, 0.95, MAT.paneel), 0, 0, 0, g);
        setze(rohr(0.04, 0.04, 0.5, 6, MAT.metall), 0.95, 0, 0, g).rotation.z = Math.PI / 2;
        break;
      }
      case 'tank': {
        setze(rohr(0.45, 0.45, 1.5, 14, MAT.weiss), 0, 0, 0, g).rotation.z = Math.PI / 2;
        setze(rohr(0.46, 0.46, 0.3, 14, MAT.orange), 0.2, 0, 0, g).rotation.z = Math.PI / 2;
        for (const s of [1, -1]) setze(new T.Mesh(new T.SphereGeometry(0.45, 12, 8, 0, Math.PI * 2, 0, Math.PI / 2), MAT.weiss), 0.75 * s, 0, 0, g).rotation.z = -s * Math.PI / 2;
        break;
      }
      case 'satellit': case 'geheim': {
        const geheim = typ === 'geheim';
        setze(kasten(1.4, 1.4, 1.8, geheim ? MAT.schwarz : MAT.gold), 0, 0, 0, g);
        for (const s of [1, -1]) {
          setze(rohr(0.05, 0.05, 0.6, 6, MAT.metall), 0.95 * s, 0, 0, g).rotation.z = Math.PI / 2;
          setze(kasten(2.6, 0.05, 1.1, geheim ? MAT.schwarz : MAT.paneel), 2.5 * s, 0, 0, g);
        }
        const sch = new T.Mesh(new T.ConeGeometry(0.55, 0.5, 14, 1, true), MAT.weiss);
        sch.material = new T.MeshPhongMaterial({ color: geheim ? 0x333333 : 0xf2f2f2, side: T.DoubleSide, flatShading: true });
        setze(sch, 0, 0, 1.15, g).rotation.x = -Math.PI / 2;
        setze(rohr(0.03, 0.03, 1.2, 5, MAT.metall), 0, 1.2, 0, g);
        blink = setze(new T.Mesh(new T.SphereGeometry(geheim ? 0.18 : 0.12, 8, 6), MAT.rot), 0, 1.85, 0, g);
        break;
      }
      case 'rakete': {
        setze(rohr(1.5, 1.5, 5.6, 18, MAT.weiss), 0, 0, 0, g);
        setze(rohr(1.52, 1.52, 0.7, 18, MAT.schwarz), 0, 1.4, 0, g);
        setze(rohr(1.52, 1.52, 0.35, 18, MAT.orange), 0, -0.6, 0, g);
        setze(rohr(0.7, 1.2, 1.1, 14, MAT.dunkel), 0, -3.3, 0, g);
        g.rotation.z = Math.PI / 2;
        break;
      }
      case 'truemmer': {
        const m = setze(new T.Mesh(new T.IcosahedronGeometry(r * 0.9, 0), MAT.glut), 0, 0, 0, g);
        m.scale.set(1, 0.55, 0.8);
        break;
      }
      case 'anzug': {
        setze(new T.Mesh(new T.SphereGeometry(0.33, 12, 10), MAT.weiss), 0, 0.62, 0, g);
        setze(new T.Mesh(new T.SphereGeometry(0.24, 12, 8, 0, Math.PI), MAT.gold), 0, 0.62, 0.12, g);
        setze(kasten(0.62, 0.8, 0.4, MAT.weiss), 0, 0, 0, g);
        setze(kasten(0.5, 0.6, 0.25, MAT.orange), 0, 0.05, -0.32, g);
        for (const s of [1, -1]) {
          setze(kasten(0.18, 0.62, 0.2, MAT.weiss), 0.42 * s, 0.05, 0, g).rotation.z = s * 0.5;
          setze(kasten(0.2, 0.7, 0.22, MAT.weiss), 0.16 * s, -0.75, 0, g);
        }
        break;
      }
    }
    return { g, blink };
  }

  const glanzMaterial = new T.SpriteMaterial({
    map: leuchtTextur([[0, 'rgba(255,255,255,1)'], [0.1, 'rgba(255,240,200,.9)'], [0.3, 'rgba(255,210,140,.25)'], [1, 'rgba(0,0,0,0)']]),
    blending: T.AdditiveBlending, depthWrite: false, depthTest: false, transparent: true, opacity: 0.7,
  });
  let teile = [];
  let naechsteId = 1;
  function teilErzeugen(typ, pos, vel, dreh) {
    const def = TYPEN[typ];
    const { g, blink } = schrottModell(typ, def.r);
    g.position.copy(pos);
    g.rotation.set(Math.random() * 6, Math.random() * 6, Math.random() * 6);
    if (def.skala) g.scale.setScalar(def.skala);
    szene.add(g);
    const glanz = new T.Sprite(glanzMaterial);
    glanz.renderOrder = 5;
    g.add(glanz);
    const t = { id: naechsteId++, typ, def, mesh: g, pos: g.position, vel: vel.clone(), dreh: dreh.clone(),
      masse: def.masse, r: def.r, wert: def.wert, weg: false, gefaehrlich: 0, blink, blinkPhase: Math.random() * 3, glanz };
    teile.push(t);
    return t;
  }
  function entfernen(t) {
    if (t.weg) return;
    t.weg = true;
    szene.remove(t.mesh);
    t.mesh.traverse(o => { if (o.geometry) o.geometry.dispose(); });
    if (spieler.gehalten === t) spieler.gehalten = null;
    if (spieler.haken && spieler.haken.teil === t) spieler.haken = null;
  }
  function feldErzeugen(nr, mitAnzug) {
    teile.forEach(entfernen);
    teile = [];
    const r = zufallsQuelle(1000 + nr * 7919);
    const plan = [
      ['schraube', 14 + 2 * nr, 8, 45], ['handschuh', 3 + Math.floor(nr / 2), 10, 50], ['pizza', 3, 10, 50],
      ['beutel', 4, 8, 45], ['tasche', 3 + Math.floor(nr / 3), 12, 55], ['paneel', 5 + Math.floor(nr / 2), 15, 65],
      ['tank', 3 + Math.floor(nr / 3), 18, 70], ['satellit', 2 + Math.floor(nr / 2), 28, 95],
      ['rakete', (nr >= 2 ? 1 : 0) + Math.floor(nr / 4), 55, 105], ['geheim', r() < 0.3 + 0.1 * nr ? 1 : 0, 85, 125],
    ];
    if (mitAnzug) plan.push(['anzug', 1, 25, 45]);
    for (const [typ, anzahl, min, max] of plan) {
      for (let i = 0; i < anzahl; i++) {
        let pos;
        for (let versuch = 0; versuch < 20; versuch++) {
          pos = zufallsRichtung(r).multiplyScalar(min + r() * (max - min));
          pos.y *= 0.75;
          if (pos.length() > 14 && teile.every(t => t.pos.distanceTo(pos) > t.r + TYPEN[typ].r + 1)) break;
        }
        const gross = TYPEN[typ].masse > 50;
        teilErzeugen(typ, pos, zufallsRichtung(r).multiplyScalar(r() * (gross ? 0.15 : 0.35)), zufallsRichtung(r).multiplyScalar(r() * (gross ? 0.2 : 0.9)));
      }
    }
  }

  // ===================== Spieler =====================
  const spieler = {
    pos: V(), vel: V(), masse: 100, r: 0.45, gier: 0, nick: 0,
    luft: 240, luftMax: 240, sprit: 100, spritMax: 100, seilMax: 35, reichweite: 45, einholTempo: 5, magnet: 0,
    angeleint: true, leck: 0, schutz: 0, gehalten: null, haken: null,
  };
  const blickQuat = new T.Quaternion(), blickEuler = new T.Euler(0, 0, 0, 'YXZ');
  const vor = V(), rechts = V(), hoch = V();
  function blickAktualisieren() {
    blickEuler.set(spieler.nick, spieler.gier, 0, 'YXZ');
    blickQuat.setFromEuler(blickEuler);
    vor.set(0, 0, -1).applyQuaternion(blickQuat);
    rechts.set(1, 0, 0).applyQuaternion(blickQuat);
    hoch.set(0, 1, 0).applyQuaternion(blickQuat);
  }
  function blickAuf(ziel) {
    _a.copy(ziel).sub(spieler.pos).normalize();
    spieler.gier = Math.atan2(-_a.x, -_a.z);
    spieler.nick = Math.asin(clamp(_a.y, -1, 1));
    blickAktualisieren();
  }
  function handPunkt(ziel) {
    return ziel.copy(spieler.pos).addScaledVector(rechts, 0.25).addScaledVector(hoch, -0.236).addScaledVector(vor, 0.65);
  }
  function guertelPunkt(ziel) {
    return ziel.set(spieler.pos.x, spieler.pos.y - 0.85, spieler.pos.z);
  }

  // Greifhaken-Gerät in der Hand
  const geraet = new T.Group();
  setze(kasten(0.055, 0.06, 0.24, MAT.dunkel), 0, 0, 0, geraet);
  setze(kasten(0.058, 0.02, 0.14, MAT.orange), 0, 0.036, 0.02, geraet);
  setze(kasten(0.045, 0.1, 0.05, MAT.dunkel), 0, -0.07, 0.07, geraet).rotation.x = 0.25;
  setze(rohr(0.016, 0.016, 0.1, 8, MAT.metall), 0, 0.005, -0.16, geraet).rotation.x = Math.PI / 2;
  const geraetLicht = setze(new T.Mesh(new T.SphereGeometry(0.012, 8, 6), MAT.blau), 0, 0.05, -0.06, geraet);
  geraet.position.set(0.25, -0.24, -0.5);
  geraet.rotation.y = 0.06;
  geraet.scale.setScalar(0.7);
  geraet.traverse(o => { if (o.isMesh) { o.renderOrder = 10; } });
  kamera.add(geraet);

  // Seil (Verlet-Kette) und Hakenseil
  const SEIL_N = 32;
  const seilPunkte = Array.from({ length: SEIL_N + 1 }, () => ({ p: V(), alt: V() }));
  let seilMesh = null;
  const letzterGuertel = V();
  function seilZuruecksetzen() {
    guertelPunkt(_b);
    letzterGuertel.copy(_b);
    seilPunkte.forEach((s, i) => { s.p.lerpVectors(ANKER, _b, i / SEIL_N); s.alt.copy(s.p); });
  }
  function ausKaestenDruecken(p, r) {
    for (const [mi, ma] of SCHIFF_KAESTEN) {
      _c.set(clamp(p.x, mi.x, ma.x), clamp(p.y, mi.y, ma.y), clamp(p.z, mi.z, ma.z));
      _d.copy(p).sub(_c);
      const l = _d.length();
      if (l < r) {
        if (l > 1e-6) { p.addScaledVector(_d, (r - l) / l); }
        else { p.y = ma.y + r; }
      }
    }
  }
  function seilSimulieren() {
    guertelPunkt(_b);
    if (_b.distanceTo(letzterGuertel) > 5) seilZuruecksetzen();
    letzterGuertel.copy(_b);
    const abstand = ANKER.distanceTo(_b);
    const laenge = clamp(abstand * 1.06 + 1.2, 2, spieler.seilMax + 0.5);
    const seg = laenge / SEIL_N;
    for (let i = 1; i < SEIL_N; i++) {
      const s = seilPunkte[i];
      _a.copy(s.p);
      s.p.x += (s.p.x - s.alt.x) * 0.96; s.p.y += (s.p.y - s.alt.y) * 0.96; s.p.z += (s.p.z - s.alt.z) * 0.96;
      s.alt.copy(_a);
    }
    seilPunkte[0].p.copy(ANKER);
    seilPunkte[SEIL_N].p.copy(_b);
    for (let iter = 0; iter < 12; iter++) {
      for (let i = 0; i < SEIL_N; i++) {
        const a = seilPunkte[i].p, b = seilPunkte[i + 1].p;
        _c.copy(b).sub(a);
        const l = _c.length() || 1e-6;
        if (l <= seg) continue;
        const diff = (l - seg) / l;
        if (i === 0) b.addScaledVector(_c, -diff);
        else if (i + 1 === SEIL_N) a.addScaledVector(_c, diff);
        else { a.addScaledVector(_c, diff * 0.5); b.addScaledVector(_c, -diff * 0.5); }
      }
      for (let i = 1; i < SEIL_N; i++) ausKaestenDruecken(seilPunkte[i].p, 0.08);
    }
    // leicht glätten, damit das Seil im All ruhig schwebt statt zu knicken
    for (let i = 1; i < SEIL_N; i++) {
      const p = seilPunkte[i].p, a = seilPunkte[i - 1].p, b = seilPunkte[i + 1].p;
      p.x += ((a.x + b.x) * 0.5 - p.x) * 0.12; p.y += ((a.y + b.y) * 0.5 - p.y) * 0.12; p.z += ((a.z + b.z) * 0.5 - p.z) * 0.12;
    }
  }
  function seilZeichnen() {
    if (seilMesh) { szene.remove(seilMesh); seilMesh.geometry.dispose(); seilMesh = null; }
    if (!spieler.angeleint || (zustand !== 'spiel' && zustand !== 'pause')) return;
    const kurve = new T.CatmullRomCurve3(seilPunkte.map(s => s.p.clone()));
    seilMesh = new T.Mesh(new T.TubeGeometry(kurve, 64, 0.03, 5, false), MAT.seil);
    szene.add(seilMesh);
  }
  const hakenSeil = new T.Mesh(new T.CylinderGeometry(0.022, 0.022, 1, 6), MAT.hakenSeil);
  const hakenKopf = new T.Mesh(new T.ConeGeometry(0.12, 0.3, 8), MAT.metall);
  hakenSeil.visible = hakenKopf.visible = false;
  szene.add(hakenSeil, hakenKopf);
  function hakenZiel() {
    const h = spieler.haken;
    return h ? (h.teil ? h.teil.pos : h.punkt) : null;
  }
  function hakenZeichnen() {
    const ziel = hakenZiel();
    if (!ziel || zustand !== 'spiel' && zustand !== 'pause') { hakenSeil.visible = hakenKopf.visible = false; return; }
    handPunkt(_a);
    _b.copy(ziel).sub(_a);
    const l = _b.length();
    hakenSeil.visible = hakenKopf.visible = true;
    hakenSeil.position.copy(_a).addScaledVector(_b, 0.5);
    hakenSeil.scale.set(1, l, 1);
    hakenSeil.quaternion.setFromUnitVectors(OBEN, _b.normalize());
    hakenKopf.position.copy(ziel).addScaledVector(_b, -0.15);
    hakenKopf.quaternion.copy(hakenSeil.quaternion);
  }

  // Funken bei Zusammenstößen
  const funken = [];
  function funkenSpruehen(pos, farbe, anzahl = 70, tempo = 9) {
    const g = new T.BufferGeometry(), p = new Float32Array(anzahl * 3), v = [];
    for (let i = 0; i < anzahl; i++) {
      p[i * 3] = pos.x; p[i * 3 + 1] = pos.y; p[i * 3 + 2] = pos.z;
      v.push(zufallsRichtung(Math.random).multiplyScalar(tempo * (0.3 + Math.random())));
    }
    g.setAttribute('position', new T.BufferAttribute(p, 3));
    const m = new T.PointsMaterial({ color: farbe, size: 0.25, transparent: true, blending: T.AdditiveBlending, depthWrite: false });
    const punkte = new T.Points(g, m);
    szene.add(punkte);
    funken.push({ punkte, v, alter: 0 });
  }
  function funkenAktualisieren(dt) {
    for (let i = funken.length - 1; i >= 0; i--) {
      const f = funken[i];
      f.alter += dt;
      const p = f.punkte.geometry.attributes.position;
      for (let k = 0; k < f.v.length; k++) { p.array[k * 3] += f.v[k].x * dt; p.array[k * 3 + 1] += f.v[k].y * dt; p.array[k * 3 + 2] += f.v[k].z * dt; }
      p.needsUpdate = true;
      f.punkte.material.opacity = Math.max(0, 1 - f.alter / 1.3);
      if (f.alter > 1.3) { szene.remove(f.punkte); f.punkte.geometry.dispose(); f.punkte.material.dispose(); funken.splice(i, 1); }
    }
  }

  // ===================== Töne =====================
  let audio = null, tonAn = true;
  function ton(freq, dauer = 0.12, typ = 'sine', laut = 0.07, bis = null, verzoegerung = 0) {
    if (!tonAn) return;
    try {
      if (!audio) audio = new (window.AudioContext || window.webkitAudioContext)();
      const t0 = audio.currentTime + verzoegerung;
      const o = audio.createOscillator(), g = audio.createGain();
      o.type = typ;
      o.frequency.setValueAtTime(freq, t0);
      if (bis) o.frequency.exponentialRampToValueAtTime(bis, t0 + dauer);
      g.gain.setValueAtTime(laut, t0);
      g.gain.exponentialRampToValueAtTime(0.0001, t0 + dauer);
      o.connect(g).connect(audio.destination);
      o.start(t0);
      o.stop(t0 + dauer + 0.02);
    } catch (e) { /* ohne Ton weiter */ }
  }

  // ===================== HUD und Meldungen =====================
  function funk(text) {
    const d = document.createElement('div');
    d.className = 'funkspruch';
    const b = document.createElement('b'); b.textContent = 'ZENTRALE';
    d.append(b, document.createTextNode(text));
    const box = $('funk');
    box.prepend(d);
    while (box.children.length > 4) box.lastChild.remove();
    setTimeout(() => d.classList.add('alt'), 9000);
    setTimeout(() => d.remove(), 10200);
    ton(1200, 0.05, 'square', 0.025);
    ton(900, 0.05, 'square', 0.025, null, 0.07);
  }
  let meldungUhr = null;
  function meldung(text, sek = 2.4) {
    const m = $('meldung');
    m.textContent = text;
    m.classList.add('zeigen');
    clearTimeout(meldungUhr);
    meldungUhr = setTimeout(() => m.classList.remove('zeigen'), sek * 1000);
  }
  function aufBildschirm(pos) {
    _a.copy(pos).project(kamera);
    if (_a.z > 1) return null;
    return { x: (_a.x * 0.5 + 0.5) * window.innerWidth, y: (-_a.y * 0.5 + 0.5) * window.innerHeight };
  }
  function schwebeText(text, pos, minus) {
    const p = aufBildschirm(pos) || { x: window.innerWidth / 2, y: window.innerHeight * 0.4 };
    const d = document.createElement('div');
    d.className = 'schwebetext' + (minus ? ' minus' : '');
    d.textContent = text;
    d.style.left = clamp(p.x, 60, window.innerWidth - 60) + 'px';
    d.style.top = clamp(p.y, 60, window.innerHeight - 60) + 'px';
    $('schwebetexte').append(d);
    setTimeout(() => d.remove(), 1600);
  }
  function schadenBlitz() {
    $('schaden').style.opacity = 1;
    setTimeout(() => { $('schaden').style.opacity = 0; }, 260);
  }

  // ===================== Zustand und Schicht =====================
  let zustand = 'laden';
  let schicht = null;
  let aktuellesZiel = { teil: null, abstand: Infinity, schiff: null };
  let einholenGedrueckt = false;
  let beendenBestaetigen = 0;

  function overlay(id) {
    for (const o of ['startbild', 'pausebild', 'endbild', 'werkstatt']) $(o).classList.toggle('versteckt', o !== id);
    $('hud').classList.toggle('versteckt', !(zustand === 'spiel' || zustand === 'pause'));
  }
  function zeigeStart() {
    zustand = 'start';
    $('start-schicht').textContent = 'Schicht ' + stand.schicht + ' · Konto ' + geld(stand.credits);
    overlay('startbild');
  }

  function schichtStarten() {
    const w = werte();
    Object.assign(spieler, {
      luftMax: w.luft, luft: w.luft, spritMax: w.sprit, sprit: w.sprit, seilMax: w.seil, reichweite: w.reichweite,
      einholTempo: w.einholen, magnet: w.magnet, angeleint: true, leck: 0, schutz: 0, gehalten: null, haken: null,
    });
    spieler.pos.set(6, 9, 10);
    spieler.vel.set(0, 0, 0);
    blickAuf(V(-12, -2, -4));
    feldErzeugen(stand.schicht, stand.alterAnzug);
    schicht = {
      nr: stand.schicht, rest: SCHICHT_DAUER, ziel: zielFuer(stand.schicht), fracht: 0, strafe: 0, zerlegt: 0,
      abgegeben: 0, zielGemeldet: false, nachtVorher: false, leckGemeldet: false, warnungen: {}, anzugGeborgen: false,
    };
    orbitZeit = 195 + (stand.schicht * 29) % 30;
    himmelAktualisieren();
    seilZuruecksetzen();
    zustand = 'spiel';
    overlay(null);
    $('funk').replaceChildren();
    setTimeout(() => funk(`Schicht ${schicht.nr}. Bring Schrott im Wert von ${geld(schicht.ziel)} in die Schleuse am Heck. Die grünen Lichter zeigen dir, wo.`), 400);
    if (stand.alterAnzug) setTimeout(() => funk('Übrigens: Dein alter Anzug treibt hier noch irgendwo herum. Bring ihn mit, das gibt eine Prämie.'), 5000);
    if (schicht.nr === 1) {
      setTimeout(() => funk('Kleiner Kram lässt sich mit E greifen. Für große Teile nimmst du den Haken.'), 11000);
      setTimeout(() => funk('Mit T scannst du die Gegend. Dann siehst du, wo Schrott treibt und was er wert ist.'), 20000);
    }
    ton(440, 0.15, 'triangle', 0.06); ton(660, 0.2, 'triangle', 0.06, null, 0.12);
    zeigerSperren();
  }

  function zeigerSperren() {
    try {
      const p = leinwand.requestPointerLock && leinwand.requestPointerLock();
      if (p && p.catch) p.catch(() => {});
    } catch (e) { /* ohne Mauszeiger-Sperre geht es mit den Pfeiltasten */ }
  }
  let hatteSperre = false;
  document.addEventListener('pointerlockchange', () => {
    const gesperrt = document.pointerLockElement === leinwand;
    if (gesperrt) hatteSperre = true;
    else if (hatteSperre && zustand === 'spiel') pause();
  });
  function pause() {
    if (zustand !== 'spiel') return;
    zustand = 'pause';
    tasten.clear();
    einholenGedrueckt = false;
    // Mauszeiger freigeben, sonst lässt sich das Pausenmenü nicht anklicken
    if (document.pointerLockElement && document.exitPointerLock) document.exitPointerLock();
    overlay('pausebild');
  }
  function weiter() {
    if (zustand !== 'pause') return;
    zustand = 'spiel';
    overlay(null);
    zeigerSperren();
  }

  function tod(grund) {
    if (zustand !== 'spiel') return;
    zustand = 'ende';
    stand.alterAnzug = true;
    speichern();
    if (document.exitPointerLock) document.exitPointerLock();
    hatteSperre = false;
    $('end-titel').textContent = 'Du bist jetzt Weltraumschrott.';
    $('end-text').textContent = grund === 'abgehaengt'
      ? 'Das Schiff ist ohne dich zurückgeflogen. Deinen Anzug sammelt die nächste Schicht ein, gegen Prämie.'
      : 'Dir ist die Luft ausgegangen. Deinen Anzug sammelt die nächste Schicht ein, gegen Prämie.';
    $('end-abrechnung').innerHTML = `<span>Fracht dieser Schicht</span><span class="minus">${geld(schicht.fracht)} verloren</span>
      <span class="summe">Auszahlung</span><span class="summe">0 €</span>`;
    ton(300, 0.6, 'sine', 0.08, 80);
    overlay('endbild');
  }

  function schichtEnde(grund) {
    if (zustand !== 'spiel') return;
    if (grund === 'zeit' && !spieler.angeleint && spieler.pos.length() > 30) { tod('abgehaengt'); return; }
    zustand = 'ende';
    if (document.exitPointerLock) document.exitPointerLock();
    hatteSperre = false;
    const s = schicht;
    const geschafft = s.fracht >= s.ziel;
    const bonus = geschafft ? Math.round(s.fracht * 0.2) : 0;
    const zeitBonus = geschafft && grund === 'station' ? Math.min(Math.round(s.rest * 0.5), Math.round(s.fracht * 0.5)) : 0;
    const auszahlung = Math.max(0, s.fracht - s.strafe + bonus + zeitBonus);
    stand.credits += auszahlung;
    stand.rekord = Math.max(stand.rekord, s.fracht);
    if (s.anzugGeborgen) stand.alterAnzug = false;
    let text;
    if (geschafft) {
      text = grund === 'station' ? 'Ziel erreicht und früh Feierabend gemacht. Die Zentrale ist zufrieden.' : 'Ziel erreicht. Gute Arbeit da draußen.';
    } else {
      stand.verwarnungen++;
      text = `Ziel verfehlt. Das ist Verwarnung ${stand.verwarnungen} von 3.`;
    }
    let gefeuert = false;
    if (stand.verwarnungen >= 3) {
      gefeuert = true;
      const rekord = stand.rekord;
      stand = standardStand();
      stand.rekord = rekord;
      text = 'Dritte Verwarnung: Die Orbit-Entsorgung GmbH hat dich gefeuert. Du fängst neu an.';
    } else {
      stand.schicht++;
    }
    speichern();
    const zeilen = [
      ['Fracht abgeliefert', geld(s.fracht), ''],
      ['Ziel', geld(s.ziel), geschafft ? 'gruen' : 'rot'],
    ];
    if (bonus) zeilen.push(['Bonus für das Ziel (+20 %)', '+' + geld(bonus), 'gruen']);
    if (zeitBonus) zeilen.push(['Früher Feierabend', '+' + geld(zeitBonus), 'gruen']);
    if (s.strafe) zeilen.push([`Strafe für ${s.zerlegt} zerlegte Satelliten`, '−' + geld(s.strafe), 'minus']);
    $('end-titel').textContent = gefeuert ? 'Gefeuert!' : geschafft ? 'Schicht geschafft!' : 'Schichtende';
    $('end-text').textContent = text;
    $('end-abrechnung').innerHTML = zeilen.map(([a, b, k]) => `<span>${a}</span><span class="${k}">${b}</span>`).join('') +
      `<span class="summe">Auszahlung</span><span class="summe">${geld(gefeuert ? 0 : auszahlung)}</span>`;
    ton(523, 0.15, 'triangle', 0.07); ton(659, 0.15, 'triangle', 0.07, null, 0.12); ton(784, 0.3, 'triangle', 0.07, null, 0.24);
    overlay('endbild');
  }

  function werkstattZeigen() {
    zustand = 'werkstatt';
    const liste = $('upgrade-liste');
    liste.replaceChildren();
    for (const u of UPGRADES) {
      const st = stufe(u.key), preis = u.preise[st];
      const zeile = document.createElement('div');
      zeile.className = 'upgrade';
      const info = document.createElement('div');
      info.innerHTML = `<b>${u.name}</b> <span class="punkte">${'●'.repeat(st)}${'○'.repeat(u.preise.length - st)}</span><br><span class="leise">${u.text}</span>`;
      const knopf = document.createElement('button');
      if (preis == null) { knopf.textContent = 'Voll ausgebaut'; knopf.disabled = true; }
      else {
        knopf.textContent = 'Kaufen · ' + geld(preis);
        knopf.disabled = stand.credits < preis;
        knopf.addEventListener('click', () => {
          if (stand.credits < preis) return;
          stand.credits -= preis;
          stand.upgrades[u.key] = st + 1;
          speichern();
          ton(880, 0.12, 'triangle', 0.06);
          werkstattZeigen();
        });
      }
      zeile.append(info, knopf);
      liste.append(zeile);
    }
    $('konto').textContent = geld(stand.credits);
    $('werkstatt-info').textContent = `Nächste Schicht: ${stand.schicht} · Ziel ${geld(zielFuer(stand.schicht))}` + (stand.verwarnungen ? ` · Verwarnungen: ${stand.verwarnungen} von 3` : '') + (stand.rekord ? ` · Rekord: ${geld(stand.rekord)}` : '');
    $('naechste-schicht').textContent = `Schicht ${stand.schicht} starten`;
    overlay('werkstatt');
  }

  // ===================== Scanner =====================
  let scanBis = 0, scanBereitAb = 0;
  const marken = [];
  const sekunden = () => performance.now() / 1000;
  function scannen() {
    if (zustand !== 'spiel') return;
    if (sekunden() < scanBereitAb) { meldung('Scanner lädt noch …', 1); return; }
    scanBis = sekunden() + 6;
    scanBereitAb = sekunden() + 10;
    const welle = $('scan-welle');
    welle.classList.remove('los');
    void welle.offsetWidth;
    welle.classList.add('los');
    ton(300, 0.6, 'sine', 0.05, 1200);
  }
  function markenAktualisieren() {
    const box = $('scanner');
    const aktiv = (zustand === 'spiel' || zustand === 'pause') && sekunden() < scanBis;
    let n = 0;
    if (aktiv) {
      for (const t of teile) {
        if (t.weg || t === spieler.gehalten || n >= 45) continue;
        const d = t.pos.distanceTo(spieler.pos);
        if (d > 160) continue;
        const p = aufBildschirm(t.pos);
        if (!p || p.x < 0 || p.y < 0 || p.x > window.innerWidth || p.y > window.innerHeight) continue;
        let m = marken[n];
        if (!m) { m = document.createElement('div'); box.append(m); marken.push(m); }
        m.style.display = 'block';
        m.style.left = p.x + 'px';
        m.style.top = p.y + 'px';
        m.className = 'marke ' + (t.wert >= 300 ? 'gold' : t.wert >= 40 ? 'gruen' : 'grau');
        m.textContent = geld(t.wert) + ' · ' + Math.round(d) + ' m';
        n++;
      }
    }
    for (let i = n; i < marken.length; i++) marken[i].style.display = 'none';
  }

  // ===================== Aktionen =====================
  function strahlKasten(start, richtung, mi, ma) {
    let tmin = 0, tmax = Infinity;
    for (const k of ['x', 'y', 'z']) {
      if (Math.abs(richtung[k]) < 1e-8) { if (start[k] < mi[k] || start[k] > ma[k]) return Infinity; continue; }
      let t1 = (mi[k] - start[k]) / richtung[k], t2 = (ma[k] - start[k]) / richtung[k];
      if (t1 > t2) { const s = t1; t1 = t2; t2 = s; }
      tmin = Math.max(tmin, t1); tmax = Math.min(tmax, t2);
      if (tmin > tmax) return Infinity;
    }
    return tmin;
  }
  function zielSuchen() {
    const start = spieler.pos;
    let bestes = null, bestT = Infinity;
    for (const t of teile) {
      if (t.weg || t === spieler.gehalten) continue;
      _a.copy(t.pos).sub(start);
      const tt = _a.dot(vor);
      if (tt < 0 || tt > 160) continue;
      const quer = _a.lengthSq() - tt * tt, rr = t.r * 1.15 + 0.25;
      if (quer < rr * rr && tt < bestT) { bestT = tt; bestes = t; }
    }
    let schiffT = Infinity;
    for (const [mi, ma] of SCHIFF_KAESTEN) schiffT = Math.min(schiffT, strahlKasten(start, vor, mi, ma));
    aktuellesZiel = { teil: bestes, abstand: bestT, schiff: schiffT < bestT && schiffT <= spieler.reichweite ? schiffT : null };
    return aktuellesZiel;
  }
  function hakenAktion() {
    if (zustand !== 'spiel') return;
    if (spieler.gehalten) { werfen(); return; }
    if (spieler.haken) { spieler.haken = null; ton(320, 0.08, 'square', 0.04); return; }
    const z = zielSuchen();
    if (z.teil && z.abstand <= spieler.reichweite + z.teil.r) {
      spieler.haken = { teil: z.teil, laenge: Math.max(z.abstand, 1.3 + z.teil.r) };
      ton(240, 0.08, 'square', 0.05, 480);
      ton(900, 0.05, 'square', 0.04, null, 0.08);
    } else if (z.schiff != null) {
      spieler.haken = { teil: null, punkt: spieler.pos.clone().addScaledVector(vor, z.schiff), laenge: z.schiff };
      ton(240, 0.08, 'square', 0.05, 480);
    } else {
      ton(150, 0.12, 'sawtooth', 0.03);
      meldung(z.teil ? 'Zu weit weg für den Haken' : 'Nichts in Reichweite', 1.2);
    }
  }
  function greifen() {
    if (zustand !== 'spiel') return;
    if (spieler.gehalten) { loslassen(); return; }
    const z = zielSuchen();
    if (!z.teil) { meldung('Nichts zum Greifen', 1.2); return; }
    if (z.abstand > 3.2 + z.teil.r) { meldung('Zu weit weg. Näher ran oder den Haken nehmen.', 1.6); return; }
    if (z.teil.masse > TRAGKRAFT) { meldung('Zu schwer zum Tragen. Zieh es mit dem Haken.', 1.8); return; }
    spieler.gehalten = z.teil;
    if (spieler.haken && spieler.haken.teil === z.teil) spieler.haken = null;
    ton(520, 0.06, 'triangle', 0.05);
  }
  function loslassen() {
    const t = spieler.gehalten;
    if (!t) return;
    spieler.gehalten = null;
    t.vel.copy(spieler.vel).addScaledVector(vor, 0.6);
    ton(400, 0.06, 'triangle', 0.04);
  }
  function werfen() {
    const t = spieler.gehalten;
    if (!t) return;
    spieler.gehalten = null;
    t.vel.copy(spieler.vel).addScaledVector(vor, 11);
    spieler.vel.addScaledVector(vor, -11 * t.masse / spieler.masse);
    t.dreh.set(Math.random() * 4 - 2, Math.random() * 4 - 2, Math.random() * 4 - 2);
    ton(200, 0.12, 'sawtooth', 0.04, 600);
  }
  function seilUmschalten() {
    if (zustand !== 'spiel') return;
    if (spieler.angeleint) {
      spieler.angeleint = false;
      meldung('Sicherungsseil gelöst!', 1.6);
      ton(220, 0.15, 'square', 0.04, 110);
      funk('Ohne Seil bist du auf dich allein gestellt. Treib nicht zu weit ab.');
    } else if (spieler.pos.distanceTo(ANKER) < 5) {
      spieler.angeleint = true;
      seilZuruecksetzen();
      meldung('Seil angelegt', 1.2);
      ton(330, 0.1, 'square', 0.04, 660);
    } else {
      meldung('Zum Anlegen musst du an den orangen Ring auf dem Schiff.', 2);
    }
  }
  function schichtBeendenVersuch() {
    if (zustand !== 'spiel') return;
    if (spieler.pos.distanceTo(STATION) > 4.5) { meldung('Schicht beenden geht nur an der Station oben auf dem Schiff.', 2); return; }
    if (schicht.fracht < schicht.ziel && performance.now() - beendenBestaetigen > 3000) {
      beendenBestaetigen = performance.now();
      meldung('Ziel noch nicht erreicht. Nochmal F zum Beenden.', 2.5);
      return;
    }
    schichtEnde('station');
  }
  function abgeben(t) {
    schicht.fracht += t.wert;
    schicht.abgegeben++;
    if (t.typ === 'anzug') { schicht.anzugGeborgen = true; funk('Dein alter Anzug ist geborgen. Ruhe in Frieden, Kollege.'); }
    schwebeText('+' + geld(t.wert), SCHLEUSE_MITTE);
    funkenSpruehen(SCHLEUSE_MITTE, 0x5dff9b, 26, 4);
    ton(660, 0.1, 'triangle', 0.06); ton(990, 0.16, 'triangle', 0.05, null, 0.09);
    entfernen(t);
    if (schicht.abgegeben === 1) funk(`Erstes Teil in der Schleuse: ${t.def.name}. Weiter so.`);
    if (!schicht.zielGemeldet && schicht.fracht >= schicht.ziel) {
      schicht.zielGemeldet = true;
      meldung('Ziel erreicht!', 2.6);
      funk('Ziel erreicht. Du kannst an der Station mit F Feierabend machen oder weitersammeln. Früher Feierabend bringt Zeitbonus.');
    }
  }
  function zerbrechen(t) {
    if (t.weg) return;
    const pos = t.pos.clone(), vel = t.vel.clone(), r = t.r;
    entfernen(t);
    schicht.zerlegt++;
    schicht.strafe += 100;
    const n = 7 + Math.floor(Math.random() * 5);
    for (let i = 0; i < n; i++) {
      const d = zufallsRichtung(Math.random);
      const f = teilErzeugen('truemmer', pos.clone().addScaledVector(d, r * 0.5), vel.clone().addScaledVector(d, 3.5 + Math.random() * 6.5),
        zufallsRichtung(Math.random).multiplyScalar(4));
      f.gefaehrlich = 8;
    }
    funkenSpruehen(pos, 0xffc36b, 120, 12);
    ton(90, 0.5, 'sawtooth', 0.12, 40);
    schwebeText('−100 € Strafe', pos, true);
    if (schicht.zerlegt === 1) funk('Ihr habt einen Satelliten zerlegt! Die Trümmer zerschlagen alles, was sie treffen. Das nennt man Kessler-Syndrom. Strafe: 100 €.');
    else funk(`Schon ${schicht.zerlegt} Satelliten zerlegt. Das wird teuer.`);
  }
  function treffer(tempo) {
    if (spieler.schutz > 0) return;
    spieler.schutz = 0.8;
    spieler.luft -= 8 + tempo * 1.2;
    spieler.leck = 6;
    schadenBlitz();
    $('riss').style.transition = 'none';
    $('riss').style.opacity = 1;
    ton(70, 0.35, 'square', 0.12, 35);
    if (!schicht.leckGemeldet) { schicht.leckGemeldet = true; funk('Dein Anzug hat ein Leck! Luft tritt aus. Zur Station, schnell!'); }
  }

  // ===================== Eingabe =====================
  const tasten = new Set();
  window.addEventListener('keydown', e => {
    if (['Space', 'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(e.code)) e.preventDefault();
    if (e.repeat) return;
    if (e.code === 'KeyM') { tonAn = !tonAn; meldung(tonAn ? 'Ton an' : 'Ton aus', 1); return; }
    if (zustand === 'pause' && (e.code === 'Escape' || e.code === 'KeyP')) { weiter(); return; }
    if (zustand !== 'spiel') return;
    tasten.add(e.code);
    switch (e.code) {
      case 'KeyE': greifen(); break;
      case 'KeyR': seilUmschalten(); break;
      case 'KeyF': schichtBeendenVersuch(); break;
      case 'KeyG': hakenAktion(); break;
      case 'KeyT': scannen(); break;
      case 'KeyQ': einholenGedrueckt = true; break;
      case 'KeyP': case 'Escape': pause(); break;
    }
  });
  window.addEventListener('keyup', e => {
    tasten.delete(e.code);
    if (e.code === 'KeyQ') einholenGedrueckt = false;
  });
  window.addEventListener('blur', () => { tasten.clear(); einholenGedrueckt = false; });
  leinwand.addEventListener('contextmenu', e => e.preventDefault());
  leinwand.addEventListener('mousedown', e => {
    if (zustand !== 'spiel') return;
    if (document.pointerLockElement !== leinwand && !hatteSperre) zeigerSperren();
    if (document.pointerLockElement !== leinwand && hatteSperre) { zeigerSperren(); return; }
    if (e.button === 0) hakenAktion();
    if (e.button === 2) einholenGedrueckt = true;
  });
  window.addEventListener('mouseup', e => { if (e.button === 2) einholenGedrueckt = false; });
  document.addEventListener('mousemove', e => {
    if (zustand !== 'spiel' || document.pointerLockElement !== leinwand) return;
    spieler.gier -= e.movementX * 0.0022;
    spieler.nick = clamp(spieler.nick - e.movementY * 0.0022, -1.5, 1.5);
  });

  $('start-knopf').addEventListener('click', schichtStarten);
  $('werkstatt-knopf').addEventListener('click', werkstattZeigen);
  $('end-werkstatt').addEventListener('click', werkstattZeigen);
  $('naechste-schicht').addEventListener('click', schichtStarten);
  $('weiter-knopf').addEventListener('click', weiter);
  $('aufgeben-knopf').addEventListener('click', () => { zustand = 'spiel'; schichtEnde('aufgegeben'); });
  $('reset-knopf').addEventListener('click', () => {
    if (!window.confirm('Spielstand wirklich zurücksetzen? Geld und Upgrades sind dann weg.')) return;
    stand = standardStand();
    speichern();
    zeigeStart();
  });

  // ===================== Physik =====================
  const SCHRITT = 1 / 60;
  function kugelGegenSchiff(pos, vel, r, abprall) {
    let getroffen = false;
    for (const [mi, ma] of SCHIFF_KAESTEN) {
      _c.set(clamp(pos.x, mi.x, ma.x), clamp(pos.y, mi.y, ma.y), clamp(pos.z, mi.z, ma.z));
      _d.copy(pos).sub(_c);
      const l = _d.length();
      if (l >= r) continue;
      if (l > 1e-6) _d.divideScalar(l);
      else {
        // Mittelpunkt im Kasten: zur nächsten Seite hinaus
        const wege = [[pos.x - mi.x, -1, 0, 0], [ma.x - pos.x, 1, 0, 0], [pos.y - mi.y, 0, -1, 0], [ma.y - pos.y, 0, 1, 0], [pos.z - mi.z, 0, 0, -1], [ma.z - pos.z, 0, 0, 1]];
        wege.sort((a, b) => a[0] - b[0]);
        _d.set(wege[0][1], wege[0][2], wege[0][3]);
        pos.addScaledVector(_d, wege[0][0]);
      }
      pos.addScaledVector(_d, r - Math.max(l, 0));
      const vn = vel.dot(_d);
      if (vn < 0) vel.addScaledVector(_d, -vn * (1 + abprall));
      getroffen = true;
    }
    return getroffen;
  }
  function inSchleuse(p) {
    return p.x > SCHLEUSE_MIN.x && p.x < SCHLEUSE_MAX.x && p.y > SCHLEUSE_MIN.y && p.y < SCHLEUSE_MAX.y && p.z > SCHLEUSE_MIN.z && p.z < SCHLEUSE_MAX.z;
  }

  function schritt(dt) {
    orbitZeit += dt;
    if (tasten.has('ArrowLeft')) spieler.gier += 1.8 * dt;
    if (tasten.has('ArrowRight')) spieler.gier -= 1.8 * dt;
    if (tasten.has('ArrowUp')) spieler.nick = clamp(spieler.nick + 1.4 * dt, -1.5, 1.5);
    if (tasten.has('ArrowDown')) spieler.nick = clamp(spieler.nick - 1.4 * dt, -1.5, 1.5);
    blickAktualisieren();

    // Düsen
    const s = spieler;
    _a.set(0, 0, 0);
    if (tasten.has('KeyW')) _a.add(vor);
    if (tasten.has('KeyS')) _a.sub(vor);
    if (tasten.has('KeyD')) _a.add(rechts);
    if (tasten.has('KeyA')) _a.sub(rechts);
    if (tasten.has('Space')) _a.add(hoch);
    if (tasten.has('KeyC')) _a.sub(hoch);
    const turbo = tasten.has('ShiftLeft') || tasten.has('ShiftRight');
    if (_a.lengthSq() > 0 && s.sprit > 0) {
      _a.normalize();
      s.vel.addScaledVector(_a, (turbo ? 7.5 : 3.4) * dt);
      s.sprit = Math.max(0, s.sprit - (turbo ? 9 : 3.2) * dt);
    }
    if (tasten.has('KeyX') && s.sprit > 0) {
      const tempo = s.vel.length();
      if (tempo > 0.01) { s.vel.multiplyScalar(Math.max(0, tempo - 6 * dt) / tempo); s.sprit = Math.max(0, s.sprit - 2.5 * dt); }
    }
    s.vel.multiplyScalar(1 - 0.03 * dt);
    s.pos.addScaledVector(s.vel, dt);

    // Sicherungsseil
    if (s.angeleint) {
      _a.copy(s.pos).sub(ANKER);
      const d = _a.length();
      if (d > s.seilMax) {
        _a.divideScalar(d);
        s.pos.copy(ANKER).addScaledVector(_a, s.seilMax);
        const vr = s.vel.dot(_a);
        if (vr > 0) s.vel.addScaledVector(_a, -vr * 1.15);
      }
    }

    // Greifhaken
    const h = s.haken;
    if (h) {
      if (h.teil && h.teil.weg) s.haken = null;
      else {
        const ziel = h.teil ? h.teil.pos : h.punkt;
        if (einholenGedrueckt) h.laenge = Math.max(h.teil ? 1.3 + h.teil.r : 1.6, h.laenge - s.einholTempo * dt);
        _a.copy(ziel).sub(s.pos);
        const d = _a.length();
        if (d > s.reichweite * 1.6) { s.haken = null; meldung('Hakenseil gerissen!', 1.5); ton(180, 0.2, 'sawtooth', 0.05, 90); }
        else if (d > h.laenge) {
          _a.divideScalar(d);
          const wS = 1 / s.masse, wT = h.teil ? 1 / h.teil.masse : 0, summe = wS + wT;
          const zuviel = d - h.laenge;
          s.pos.addScaledVector(_a, zuviel * wS / summe);
          if (h.teil) h.teil.pos.addScaledVector(_a, -zuviel * wT / summe);
          const vRel = (h.teil ? h.teil.vel.dot(_a) : 0) - s.vel.dot(_a);
          if (vRel > 0) {
            const J = vRel / summe;
            s.vel.addScaledVector(_a, J * wS);
            if (h.teil) {
              h.teil.vel.addScaledVector(_a, -J * wT);
              if (h.teil.def.zerbrechlich && vRel > 7.5) zerbrechen(h.teil);
            }
          }
        }
      }
    }

    // Spieler gegen Schiff
    kugelGegenSchiff(s.pos, s.vel, s.r, 0.2);

    // Gehaltenes Teil schwebt vor dem Helm
    if (s.gehalten) {
      const t = s.gehalten;
      _b.copy(s.pos).addScaledVector(vor, 1.3 + t.r).addScaledVector(hoch, -0.35);
      t.pos.lerp(_b, 0.35);
      t.vel.copy(s.vel);
      t.dreh.multiplyScalar(0.9);
    }

    // Luft, Leck, Station
    s.schutz = Math.max(0, s.schutz - dt);
    s.luft -= dt * (s.leck > 0 ? 3 : 1);
    if (s.leck > 0) { s.leck -= dt; if (s.leck <= 0) { $('riss').style.transition = 'opacity 1.2s'; $('riss').style.opacity = 0; } }
    const anStation = s.pos.distanceTo(STATION) < 4;
    if (anStation) {
      s.luft = Math.min(s.luftMax, s.luft + 45 * dt);
      s.sprit = Math.min(s.spritMax, s.sprit + 40 * dt);
      if (s.leck > 0) { s.leck = 0; $('riss').style.transition = 'opacity 1.2s'; $('riss').style.opacity = 0; }
    }
    if (s.luft <= 0) { s.luft = 0; tod('luft'); return; }

    teileBewegen(dt);

    // Schicht-Zeit und Warnungen
    const sch = schicht;
    sch.rest -= dt;
    const w = sch.warnungen;
    if (!w.minute && sch.rest < 60) { w.minute = true; funk('Noch eine Minute! Wer nicht am Schiff ist, bleibt draußen.'); }
    if (!w.luft && s.luft < s.luftMax * 0.25) { w.luft = true; funk('Deine Luft wird knapp. Ab zur Station oben auf dem Schiff.'); }
    if (s.luft > s.luftMax * 0.5) w.luft = false;
    if (!w.weit && !s.angeleint && s.pos.length() > 160) { w.weit = true; funk('Du treibst ganz schön weit weg. Ohne Seil holt dich keiner.'); }
    if (s.luft < s.luftMax * 0.15 && Math.floor(sch.rest * 2) % 2 === 0 && !w.piep) { w.piep = true; ton(880, 0.08, 'square', 0.04); }
    if (Math.floor(sch.rest * 2) % 2 === 1) w.piep = false;
    const istNacht = nacht > 0.5;
    if (istNacht !== sch.nachtVorher) {
      sch.nachtVorher = istNacht;
      if (istNacht) funk('Ihr fliegt in den Erdschatten. Ab jetzt hilft nur die Helmlampe.');
      else funk('Sonnenaufgang! In 45 Minuten geht die Sonne hier oben schon wieder unter.');
    }
    if (sch.rest <= 0) schichtEnde('zeit');
  }

  function teileBewegen(dt) {
    const s = spieler;
    for (const t of teile) {
      if (t.weg) continue;
      if (t !== s.gehalten) t.pos.addScaledVector(t.vel, dt);
      t.mesh.rotation.x += t.dreh.x * dt; t.mesh.rotation.y += t.dreh.y * dt; t.mesh.rotation.z += t.dreh.z * dt;
      if (t.gefaehrlich > 0) {
        t.gefaehrlich -= dt;
        if (t.gefaehrlich <= 0) t.mesh.traverse(o => { if (o.isMesh && o.material === MAT.glut) o.material = MAT.truemmer; });
      }
      if (s.magnet > 0 && t !== s.gehalten) {
        _a.copy(SCHLEUSE_MITTE).sub(t.pos);
        const d = _a.length();
        if (d < s.magnet && d > 0.01) t.vel.addScaledVector(_a, 3 * dt * (1 - d / s.magnet) / d);
      }
      if (inSchleuse(t.pos)) { abgeben(t); continue; }
      if (kugelGegenSchiff(t.pos, t.vel, t.r, 0.3)) t.dreh.multiplyScalar(0.92);
      if (t.pos.lengthSq() > 900 * 900) entfernen(t);
    }
    // Teile untereinander und gegen den Spieler
    const n = teile.length;
    for (let i = 0; i < n; i++) {
      const a = teile[i];
      if (a.weg) continue;
      for (let j = i + 1; j < n; j++) {
        if (a.weg) break;
        const b = teile[j];
        if (b.weg) continue;
        const rr = a.r + b.r;
        const dx = b.pos.x - a.pos.x, dy = b.pos.y - a.pos.y, dz = b.pos.z - a.pos.z;
        const d2 = dx * dx + dy * dy + dz * dz;
        if (d2 >= rr * rr || d2 < 1e-10) continue;
        const d = Math.sqrt(d2);
        _a.set(dx / d, dy / d, dz / d);
        const wA = a === s.gehalten ? 0 : 1 / a.masse, wB = b === s.gehalten ? 0 : 1 / b.masse, summe = wA + wB;
        if (summe === 0) continue;
        const ueber = rr - d;
        a.pos.addScaledVector(_a, -ueber * wA / summe);
        b.pos.addScaledVector(_a, ueber * wB / summe);
        const vn = b.vel.dot(_a) - a.vel.dot(_a);
        if (vn < 0) {
          const J = -(1 + 0.4) * vn / summe;
          a.vel.addScaledVector(_a, -J * wA);
          b.vel.addScaledVector(_a, J * wB);
          if (-vn > 4.5) {
            if (a.def.zerbrechlich) zerbrechen(a);
            if (b.def.zerbrechlich) zerbrechen(b);
          }
          if (-vn > 2.5 && -vn <= 4.5) ton(140 + Math.random() * 60, 0.06, 'square', 0.02);
        }
      }
      if (a.weg || a === s.gehalten) continue;
      const rr = a.r + s.r;
      _a.copy(s.pos).sub(a.pos);
      const d = _a.length();
      if (d < rr && d > 1e-6) {
        _a.divideScalar(d);
        const wA = 1 / a.masse, wS = 1 / s.masse, summe = wA + wS;
        a.pos.addScaledVector(_a, -(rr - d) * wA / summe);
        s.pos.addScaledVector(_a, (rr - d) * wS / summe);
        const vn = s.vel.dot(_a) - a.vel.dot(_a);
        if (vn < 0) {
          const J = -(1 + 0.3) * vn / summe;
          a.vel.addScaledVector(_a, -J * wA);
          s.vel.addScaledVector(_a, J * wS);
          if (-vn > 5.5 && (a.masse >= 2 || a.gefaehrlich > 0)) treffer(-vn);
        }
      }
    }
    if (teile.length > 40 && teile.some(t => t.weg)) teile = teile.filter(t => !t.weg);
  }

  // Im Menü treibt der Schrott nur ruhig weiter
  function leerlauf(dt) {
    orbitZeit += dt * 0.6;
    for (const t of teile) {
      if (t.weg) continue;
      t.pos.addScaledVector(t.vel, dt);
      t.mesh.rotation.x += t.dreh.x * dt; t.mesh.rotation.y += t.dreh.y * dt;
    }
  }

  // ===================== Darstellung =====================
  let hudUhr = 0;
  function hudAktualisieren() {
    const s = spieler, sch = schicht;
    if (!sch) return;
    const luftAnteil = clamp(s.luft / s.luftMax, 0, 1), spritAnteil = clamp(s.sprit / s.spritMax, 0, 1);
    $('luft-balken').firstChild.style.width = (luftAnteil * 100) + '%';
    $('luft-balken').classList.toggle('warnung', luftAnteil < 0.25 || s.leck > 0);
    $('luft-text').textContent = zeitText(s.luft) + (s.leck > 0 ? ' LECK' : '');
    $('sprit-balken').firstChild.style.width = (spritAnteil * 100) + '%';
    $('sprit-balken').classList.toggle('warnung', spritAnteil < 0.15);
    $('sprit-text').textContent = Math.round(spritAnteil * 100) + ' %';
    const seil = $('seil-text');
    if (s.angeleint) { seil.textContent = Math.round(s.pos.distanceTo(ANKER)) + ' / ' + s.seilMax + ' m'; seil.classList.remove('los'); }
    else { seil.textContent = 'OHNE SEIL · ' + Math.round(s.pos.length()) + ' m vom Schiff'; seil.classList.add('los'); }
    $('tempo-text').textContent = s.vel.length().toFixed(1) + ' m/s';
    $('schicht-titel').textContent = 'Schicht ' + sch.nr;
    $('zeit').textContent = zeitText(sch.rest);
    $('zeit').classList.toggle('knapp', sch.rest < 60);
    $('fracht-text').textContent = 'Fracht ' + geld(sch.fracht) + ' / Ziel ' + geld(sch.ziel);
    $('fracht-balken').firstChild.style.width = clamp(sch.fracht / sch.ziel, 0, 1) * 100 + '%';
    $('nacht-hinweis').textContent = nacht > 0.5 ? 'Im Erdschatten' : '';
    const bereitIn = scanBereitAb - sekunden();
    $('scan-text').textContent = bereitIn > 0 ? 'Scanner lädt · ' + Math.ceil(bereitIn) + ' s' : 'Scanner bereit · T';

    // Ziel und Hinweise
    const z = zielSuchen();
    const rahmen = $('zielrahmen'), info = $('zielinfo');
    const kreuz = $('fadenkreuz');
    const hinweise = [];
    if (z.teil && !s.gehalten) {
      const t = z.teil, p = aufBildschirm(t.pos);
      const inReichweite = z.abstand <= s.reichweite + t.r;
      if (p) {
        const groesseRahmen = clamp(t.r / Math.max(z.abstand, 0.5) * window.innerHeight * 0.9, 26, 260);
        rahmen.style.display = 'block';
        rahmen.style.left = (p.x - groesseRahmen / 2) + 'px'; rahmen.style.top = (p.y - groesseRahmen / 2) + 'px';
        rahmen.style.width = rahmen.style.height = groesseRahmen + 'px';
        rahmen.classList.toggle('weit', !inReichweite);
      } else rahmen.style.display = 'none';
      info.innerHTML = `${t.def.name} · <b>${geld(t.wert)}</b> · ${Math.round(z.abstand)} m`;
      kreuz.classList.toggle('aktiv', inReichweite);
      if (z.abstand <= 3.2 + t.r && t.masse <= TRAGKRAFT) hinweise.push(['E', 'Greifen']);
      else if (inReichweite && !s.haken) hinweise.push(['Klick', 'Haken schießen']);
    } else {
      rahmen.style.display = 'none';
      info.textContent = z.schiff != null && !s.haken ? 'Schiff · Haken zum Heranziehen' : '';
      kreuz.classList.toggle('aktiv', z.schiff != null);
    }
    if (s.gehalten) hinweise.push(['Klick', 'Werfen'], ['E', 'Loslassen']);
    if (s.haken) hinweise.push(['Rechtsklick / Q', 'Einholen'], ['Klick', 'Haken lösen']);
    const anStation = s.pos.distanceTo(STATION) < 4;
    if (anStation) hinweise.push(['', 'Tanke Luft und Treibstoff'], ['F', 'Schicht beenden']);
    if (!s.angeleint && s.pos.distanceTo(ANKER) < 5) hinweise.push(['R', 'Seil anlegen']);
    const box = $('hinweise');
    box.replaceChildren(...hinweise.map(([k, txt]) => {
      const d = document.createElement('span'); d.className = 'taste';
      if (k) { const kb = document.createElement('kbd'); kb.textContent = k; d.append(kb); }
      d.append(document.createTextNode(txt));
      return d;
    }));
  }

  let blinkZeit = 0;
  function darstellen(dt) {
    blinkZeit += dt;
    himmelAktualisieren();
    if (zustand === 'spiel' || zustand === 'pause') {
      kamera.position.copy(spieler.pos);
      kamera.quaternion.copy(blickQuat);
      geraet.visible = true;
      geraetLicht.material = spieler.haken ? MAT.gruen : MAT.blau;
      if (zustand === 'spiel') seilSimulieren();
      seilZeichnen();
      hakenZeichnen();
      hudUhr -= dt;
      if (hudUhr <= 0) { hudUhr = 0.08; hudAktualisieren(); }
      markenAktualisieren();
    } else {
      const w = performance.now() * 0.00004;
      kamera.position.set(Math.cos(w) * 40, 13, Math.sin(w) * 40);
      kamera.lookAt(-2, -1, 0);
      geraet.visible = false;
      seilZeichnen();
      hakenZeichnen();
    }
    navLichter.forEach((l, i) => { l.visible = (blinkZeit + i * 0.5) % 1.4 < 0.25; });
    glanzMaterial.opacity = 0.75 * (1 - 0.8 * nacht);
    for (const t of teile) {
      if (t.weg) continue;
      if (t.blink) t.blink.visible = (blinkZeit + t.blinkPhase) % (t.typ === 'geheim' ? 0.6 : 1.2) < 0.15;
      const abstand = t.pos.distanceTo(kamera.position);
      t.glanz.visible = abstand > 9 && t !== spieler.gehalten;
      const funkeln = 0.75 + 0.25 * Math.sin(blinkZeit * 2.3 + t.blinkPhase * 7);
      t.glanz.scale.setScalar((0.8 + t.r * 1.6 + abstand * 0.018) * funkeln / (t.def.skala || 1));
    }
    funkenAktualisieren(dt);
    renderer.render(szene, kamera);
  }

  const SCHRITTE_MAX = 6;
  let letzte = performance.now(), akku = 0;
  function rahmen(jetzt) {
    requestAnimationFrame(rahmen);
    const dt = Math.min(0.1, (jetzt - letzte) / 1000);
    letzte = jetzt;
    if (zustand === 'spiel') {
      akku += dt;
      let n = 0;
      while (akku >= SCHRITT && n < SCHRITTE_MAX && zustand === 'spiel') { schritt(SCHRITT); akku -= SCHRITT; n++; }
      if (n === SCHRITTE_MAX) akku = 0;
    } else if (zustand !== 'pause') {
      leerlauf(dt);
    }
    darstellen(dt);
  }

  // ===================== Start =====================
  feldErzeugen(1, false);
  himmelAktualisieren();
  requestAnimationFrame(rahmen);
  zeigeStart();
  erdKartenErzeugen(anteil => { $('ladebalken').firstChild.style.width = Math.round(anteil * 100) + '%'; }).then(() => {
    $('ladebalken').style.visibility = 'hidden';
    const k = $('start-knopf');
    k.disabled = false;
    k.textContent = 'Schicht ' + stand.schicht + ' starten';
    zustand = zustand === 'laden' ? 'start' : zustand;
  });

  // ===================== Test-Schnittstelle =====================
  window.MUELL = {
    get zustand() { return zustand; },
    get spieler() { return spieler; },
    get teile() { return teile.filter(t => !t.weg); },
    get schicht() { return schicht; },
    get stand() { return stand; },
    get nacht() { return nacht; },
    starten: schichtStarten,
    werkstatt: werkstattZeigen,
    schritt(sek) { const n = Math.round(sek / SCHRITT); for (let i = 0; i < n && zustand === 'spiel'; i++) schritt(SCHRITT); },
    taste(code, an) { if (an) tasten.add(code); else tasten.delete(code); },
    einholen(an) { einholenGedrueckt = !!an; },
    blickAuf(ziel) { blickAuf(ziel); },
    haken: hakenAktion,
    greifen,
    werfen,
    seil: seilUmschalten,
    beenden: schichtBeendenVersuch,
    zielSuchen: () => zielSuchen(),
    setzeOrbitZeit(sek) { orbitZeit = sek; himmelAktualisieren(); },
    teilErzeugen: (typ, pos, vel) => teilErzeugen(typ, pos, vel || V(), V()),
    V,
    ANKER, STATION, SCHLEUSE_MITTE,
  };
})();
