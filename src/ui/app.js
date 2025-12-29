const state = {
    sessionId: null,
    currentImageBlob: null,
    imageWidth: 0,
    imageHeight: 0,
    selection: null,
    detectedItems: [],
    layers: [],
    selectedLayerId: null,
    isDragging: false,
    dragMode: null, // 'rect', 'layer'
    dragStart: { x: 0, y: 0 },
    dragOffset: { x: 0, y: 0 },
    activeTool: null
};

const dom = {
    views: {
        upload: document.getElementById('upload-view'),
        editor: document.getElementById('editor-view')
    },
    canvas: document.getElementById('editor-canvas'),
    status: document.getElementById('status'),
    fileInput: document.getElementById('file-upload'),
    layersList: document.getElementById('layers-list')
};

const ctx = dom.canvas.getContext('2d');

// --- API ---
async function api(endpoint, method = 'GET', body = null) {
    const opts = { method };
    if (body) {
        opts.headers = { 'Content-Type': 'application/json' };
        opts.body = JSON.stringify(body);
    }
    const res = await fetch(endpoint, opts);
    if (!res.ok) throw new Error(await res.text());
    return res.json();
}

async function uploadFile(file) {
    const fd = new FormData();
    fd.append('file', file);
    const res = await fetch('/upload', { method: 'POST', body: fd });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
}

// --- APP FLOW ---

function setStatus(msg) {
    dom.status.textContent = msg;
    setTimeout(() => dom.status.textContent = 'Ready', 3000);
}

function switchView(viewName) {
    Object.values(dom.views).forEach(v => v.classList.remove('active'));
    dom.views[viewName].classList.add('active');
}

async function initSession(sessionId) {
    state.sessionId = sessionId;
    switchView('editor');
    await refreshImage();
}

async function loadStock(color) {
    try {
        const res = await api(`/stock/${color}`, 'POST');
        await initSession(res.session_id);
    } catch (e) {
        alert(e.message);
    }
}

dom.fileInput.addEventListener('change', async (e) => {
    if (!e.target.files[0]) return;
    try {
        const res = await uploadFile(e.target.files[0]);
        await initSession(res.session_id);
    } catch (e) {
        alert("Upload failed: " + e.message);
    }
});

async function refreshImage() {
    const res = await fetch(`/session/${state.sessionId}/image?t=${Date.now()}`);
    if (!res.ok) return;
    const blob = await res.blob();
    const bmp = await createImageBitmap(blob);

    state.currentImageBlob = bmp;
    state.imageWidth = bmp.width;
    state.imageHeight = bmp.height;

    dom.canvas.width = bmp.width;
    dom.canvas.height = bmp.height;

    await fetchLayers();
    draw();
}

async function fetchLayers() {
    try {
        state.layers = await api(`/session/${state.sessionId}/layers`);
        updateLayersUI();
    } catch (e) {
        console.error("Failed to fetch layers", e);
    }
}

function updateLayersUI() {
    if (!dom.layersList) return;
    dom.layersList.innerHTML = state.layers.map((l) => `
        <div class="layer-item" 
             style="padding: 8px; background: ${l.id === state.selectedLayerId ? '#444' : '#333'}; cursor: pointer; border-bottom: 1px solid #555; width: 100%; box-sizing: border-box;"
             onclick="selectLayer('${l.id}')">
            <div style="font-weight: bold;">${l.name}</div>
            <div style="font-size: 0.8em; color: #aaa;">${l.type} ${l.visible ? '' : '(hidden)'}</div>
        </div>
    `).reverse().join('');
}

window.selectLayer = (id) => {
    state.selectedLayerId = id;
    state.selection = null;
    draw();
    updateLayersUI();

    // Update Text Controls UI
    const controls = document.getElementById('text-controls');
    if (!controls) return;

    const l = state.layers.find(l => l.id === id);
    if (l && l.type === 'text') {
        controls.style.display = 'block';
        if (l.font_size) document.getElementById('font-size').value = l.font_size;

        if (l.font_color) {
            const [r, g, b] = l.font_color;
            const hex = "#" + ((1 << 24) + (r << 16) + (g << 8) + b).toString(16).slice(1);
            document.getElementById('font-color').value = hex;
        }
    } else {
        controls.style.display = 'none';
    }
}

window.updateTextStyle = async () => {
    if (!state.selectedLayerId) return;
    const size = parseInt(document.getElementById('font-size').value);
    const colorHex = document.getElementById('font-color').value;

    // Hex to RGB
    const r = parseInt(colorHex.substr(1, 2), 16);
    const g = parseInt(colorHex.substr(3, 2), 16);
    const b = parseInt(colorHex.substr(5, 2), 16);

    try {
        await api(`/session/${state.sessionId}/layers/${state.selectedLayerId}`, 'PUT', {
            font_size: size,
            font_color: [r, g, b]
        });
        await refreshImage();
    } catch (e) {
        console.error(e);
    }
};

// --- TOOLS ---

window.setTool = (tool) => {
    state.activeTool = tool;
    document.querySelectorAll('.btn.tool').forEach(b => b.classList.remove('active'));
    const btn = document.getElementById(`tool-${tool}`);
    if (btn) btn.classList.add('active');

    if (state.selection && tool !== 'lift' && tool !== 'magic-remove') {
        executeTool();
    }
};

window.detect = async (type) => {
    try {
        setStatus(`Detecting ${type}...`);
        const res = await api(`/session/${state.sessionId}/detect/${type}`, 'POST');
        state.detectedItems = res.items; // These are just overlays
        setStatus(`Found ${res.items.length} items`);
        draw();
    } catch (e) {
        alert(e.message);
        setStatus("Detection failed");
    }
};

async function executeTool() {
    if (!state.selection || !state.activeTool) return;

    const { x, y, w, h } = state.selection;
    if (w === 0 || h === 0) return;

    const req = {
        operation: "",
        mask: { type: "rect", x, y, width: w, height: h },
        params: {}
    };

    switch (state.activeTool) {
        case 'fill':
            req.operation = "fill";
            req.params.color = [255, 0, 0];
            break;
        case 'harmonize':
            req.operation = "harmonize";
            req.params.brightness = 1.5;
            break;
        case 'move':
            req.operation = "move";
            req.params.dx = 50;
            req.params.dy = 0;
            break;
        default:
            return;
    }

    try {
        setStatus("Applying edit...");
        await api(`/session/${state.sessionId}/edit`, 'POST', req);
        state.selection = null;
        document.querySelectorAll('.btn.tool').forEach(b => b.classList.remove('active'));
        state.activeTool = null;
        await refreshImage();
        setStatus("Edit applied");
    } catch (e) {
        alert(e.message);
    }
}

window.actions = {
    undo: async () => {
        await api(`/session/${state.sessionId}/undo`, 'POST');
        await refreshImage();
    },
    redo: async () => {
        await api(`/session/${state.sessionId}/redo`, 'POST');
        await refreshImage();
    }
};

// --- CANVAS INTERACTION ---

function getPos(e) {
    const rect = dom.canvas.getBoundingClientRect();
    const scaleX = dom.canvas.width / rect.width;
    const scaleY = dom.canvas.height / rect.height;
    return {
        x: (e.clientX - rect.left) * scaleX,
        y: (e.clientY - rect.top) * scaleY
    };
}

dom.canvas.addEventListener('mousedown', async (e) => {
    const pos = getPos(e);

    // 1. Lift Tool
    if (state.activeTool === 'lift') {
        try {
            setStatus("Lifting...");
            const res = await api(`/session/${state.sessionId}/layers/lift`, 'POST', { x: Math.floor(pos.x), y: Math.floor(pos.y) });
            await refreshImage();
            setStatus(`Lifted ${res.type}`);
            selectLayer(res.layer_id);
            window.setTool('move');
        } catch (e) {
            alert(e.message);
            setStatus("Lift failed");
        }
        return;
    }

    // 2. Magic Remove
    if (state.activeTool === 'magic-remove') {
        try {
            setStatus("Removing object...");
            await api(`/session/${state.sessionId}/edit/magic-remove`, 'POST', { x: Math.floor(pos.x), y: Math.floor(pos.y) });
            await refreshImage();
            setStatus("Object removed");
        } catch (e) {
            alert(e.message);
            setStatus("Removal failed");
        }
        return;
    }

    // 3. Layer Hit Test (Top-down)
    let hitLayerId = null;
    for (let i = state.layers.length - 1; i >= 0; i--) {
        const l = state.layers[i];
        if (l.type === 'image') continue;

        let lw = l.width;
        let lh = l.height;
        if (l.type === 'text') {
            // Calculate dims if not present (handled in draw)
            if (!lw) {
                ctx.font = `${l.font_size}px ${l.font_family || 'Arial'}`;
                lw = ctx.measureText(l.text).width;
                lh = l.font_size;
                // Cache
                l.width = lw; l.height = lh;
            }
        }

        if (pos.x >= l.x && pos.x <= l.x + lw && pos.y >= l.y && pos.y <= l.y + lh) {
            hitLayerId = l.id;
            break;
        }
    }

    if (hitLayerId) {
        selectLayer(hitLayerId);
        if (state.activeTool === 'move') {
            state.isDragging = true;
            state.dragMode = 'layer';
            state.dragStart = pos;
            state.dragOffset = { x: 0, y: 0 };
            return;
        }
    } else {
        if (state.activeTool !== 'move') state.selectedLayerId = null;
        updateLayersUI();
    }

    // 4. Rect Selection
    state.isDragging = true;
    state.dragMode = 'rect';
    state.dragStart = pos; // reuse dragStart for rect origin
    state.selection = { x: pos.x, y: pos.y, w: 0, h: 0 };
    draw();
});

dom.canvas.addEventListener('mousemove', (e) => {
    if (!state.isDragging) return;
    const pos = getPos(e);

    if (state.dragMode === 'layer' && state.selectedLayerId) {
        state.dragOffset = {
            x: pos.x - state.dragStart.x,
            y: pos.y - state.dragStart.y
        };
        draw();
    } else if (state.dragMode === 'rect') {
        const w = pos.x - state.dragStart.x;
        const h = pos.y - state.dragStart.y;
        state.selection = {
            x: w > 0 ? state.dragStart.x : pos.x,
            y: h > 0 ? state.dragStart.y : pos.y,
            w: Math.abs(w),
            h: Math.abs(h)
        };
        draw();
    }
});

dom.canvas.addEventListener('mouseup', async () => {
    if (!state.isDragging) return;
    state.isDragging = false;

    if (state.dragMode === 'layer' && state.selectedLayerId) {
        const { x, y } = state.dragOffset;
        if (x !== 0 || y !== 0) {
            setStatus("Moving...");
            try {
                await api(`/session/${state.sessionId}/layers/${state.selectedLayerId}`, 'PUT', { dx: Math.floor(x), dy: Math.floor(y) });
                await refreshImage();
                setStatus("Moved");
            } catch (e) {
                alert(e.message);
            }
        }
        state.dragOffset = { x: 0, y: 0 };
        draw();
    } else if (state.dragMode === 'rect') {
        if (state.selection) {
            state.selection.x = Math.floor(state.selection.x);
            state.selection.y = Math.floor(state.selection.y);
            state.selection.w = Math.floor(state.selection.w);
            state.selection.h = Math.floor(state.selection.h);
            if (state.activeTool && state.activeTool !== 'move') executeTool();
        }
    }
});

window.addLayer = async (file) => {
    if (!file) return;
    try {
        setStatus("Adding layer...");
        const fd = new FormData();
        fd.append('file', file);
        fd.append('x', Math.floor(dom.canvas.width / 2 - 50));
        fd.append('y', Math.floor(dom.canvas.height / 2 - 50));

        const res = await fetch(`/session/${state.sessionId}/layers/add`, { method: 'POST', body: fd });
        if (!res.ok) throw new Error(await res.text());
        const data = await res.json();

        await refreshImage();
        setStatus("Layer added");
        selectLayer(data.layer_id);
    } catch (e) {
        alert(e.message);
    }
};

window.replaceLayer = async (file) => {
    if (!file || !state.selectedLayerId) return;
    try {
        setStatus("Replacing layer content...");
        const fd = new FormData();
        fd.append('file', file);

        const res = await fetch(`/session/${state.sessionId}/layers/${state.selectedLayerId}/replace`, { method: 'POST', body: fd });
        if (!res.ok) throw new Error(await res.text());

        await refreshImage();
        setStatus("Layer updated");
    } catch (e) {
        alert(e.message);
    }
};

dom.canvas.addEventListener('dblclick', async (e) => {
    if (!state.selectedLayerId) return;
    const l = state.layers.find(l => l.id === state.selectedLayerId);
    if (!l || l.type !== 'text') return;

    const newText = prompt("Edit Text:", l.text);
    if (newText !== null && newText !== l.text) {
        try {
            await api(`/session/${state.sessionId}/layers/${l.id}`, 'PUT', { text: newText });
            await refreshImage();
        } catch (e) {
            alert(e.message);
        }
    }
});

function draw() {
    ctx.clearRect(0, 0, dom.canvas.width, dom.canvas.height);

    // Image
    if (state.currentImageBlob) {
        ctx.drawImage(state.currentImageBlob, 0, 0);
    }

    // Layers (Overlay Box)
    state.layers.forEach(l => {
        if (l.type === 'image') return;

        let lx = l.x;
        let ly = l.y;
        // Apply drag offset
        if (state.isDragging && state.dragMode === 'layer' && l.id === state.selectedLayerId) {
            lx += state.dragOffset.x;
            ly += state.dragOffset.y;
        }

        let lw = l.width;
        let lh = l.height;
        if (l.type === 'text') {
            ctx.font = `${l.font_size}px ${l.font_family || 'Arial'}`;
            lw = ctx.measureText(l.text).width;
            lh = l.font_size;
            // Update cache
            l.width = lw; l.height = lh;
        }

        const isSelected = l.id === state.selectedLayerId;

        if (isSelected) {
            ctx.strokeStyle = '#00f';
            ctx.lineWidth = 2;
            ctx.strokeRect(lx, ly, lw, lh);
            // Handles?
            ctx.fillStyle = '#fff';
            ctx.fillRect(lx - 3, ly - 3, 6, 6);
            ctx.fillRect(lx + lw - 3, ly + lh - 3, 6, 6);
        }
    });

    // Selection
    if (state.selection) {
        const { x, y, w, h } = state.selection;
        ctx.strokeStyle = '#fff';
        ctx.lineWidth = 1;
        ctx.setLineDash([5, 5]);
        ctx.strokeRect(x, y, w, h);
        ctx.setLineDash([]);
    }

    // Detected Items Overlays
    state.detectedItems.forEach(item => {
        const { x, y, w, h } = item.box;
        ctx.strokeStyle = '#0f0';
        ctx.lineWidth = 2;
        ctx.strokeRect(x, y, w, h);
    });
}
