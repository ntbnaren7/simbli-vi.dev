const state = {
    sessionId: null,
    currentImageBlob: null,
    imageWidth: 0,
    imageHeight: 0,
    selection: null, // {x,y,w,h}
    detectedItems: [],
    layers: [],
    selectedLayerId: null,
    isDragging: false,
    dragMode: null, // 'rect', 'layer'
    dragStart: { x: 0, y: 0 },
    dragOffset: { x: 0, y: 0 },
    activeTool: 'select'
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
    // Auto-detect text on load/upload
    await detect('text');
}

window.loadStock = async (color) => {
    try {
        const res = await api(`/stock/${color}`, 'POST');
        await initSession(res.session_id);
    } catch (e) { alert(e.message); }
};

dom.fileInput.addEventListener('change', async (e) => {
    if (!e.target.files[0]) return;
    try {
        const res = await uploadFile(e.target.files[0]);
        await initSession(res.session_id);
    } catch (e) { alert("Upload failed: " + e.message); }
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
    } catch (e) { console.error(e); }
}

function updateLayersUI() {
    if (!dom.layersList) return;
    dom.layersList.innerHTML = state.layers.map((l) => `
        <div class="layer-item ${l.id === state.selectedLayerId ? 'selected' : ''}" 
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

window.editSelectedText = async () => {
    if (!state.selectedLayerId) return;
    const l = state.layers.find(l => l.id === state.selectedLayerId);
    if (l && l.type === 'text') {
        const newText = prompt("Edit text:", l.text);
        if (newText && newText !== l.text) {
            await api(`/session/${state.sessionId}/layers/${state.selectedLayerId}`, 'PUT', { text: newText });
            await refreshImage();
        }
    }
}

// --- TOOLS ---

window.setTool = (tool) => {
    state.activeTool = tool;
    document.querySelectorAll('.btn.tool').forEach(b => b.classList.remove('active'));
    const btn = document.getElementById(`tool-${tool}`);
    if (btn) btn.classList.add('active');
};

window.detect = async (type) => {
    try {
        setStatus(`Detecting ${type}...`);
        const res = await api(`/session/${state.sessionId}/detect/${type}`, 'POST');
        state.detectedItems = res.items;
        setStatus(`Found ${res.items.length} items`);
        draw();
    } catch (e) {
        setStatus("Detection failed");
    }
};

window.actions = {
    undo: async () => { await api(`/session/${state.sessionId}/undo`, 'POST'); await refreshImage(); },
    redo: async () => { await api(`/session/${state.sessionId}/redo`, 'POST'); await refreshImage(); }
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
            window.setTool('select'); // Auto-switch to select
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
        if (l.type === 'text' && !lw) {
            ctx.font = `${l.font_size}px ${l.font_family || 'Arial'}`;
            lw = ctx.measureText(l.text).width;
            lh = l.font_size;
            // Cache
            l.width = lw; l.height = lh;
        }

        if (pos.x >= l.x && pos.x <= l.x + lw && pos.y >= l.y && pos.y <= l.y + lh) {
            hitLayerId = l.id;
            break;
        }
    }

    // 3.5 Detected Items (Auto Select)
    if (!hitLayerId && (state.activeTool === 'select' || state.activeTool === 'text')) {
        let hitItem = null;
        for (let item of state.detectedItems) {
            const b = item.box;
            if (pos.x >= b.x && pos.x <= b.x + b.w && pos.y >= b.y && pos.y <= b.y + b.h) {
                hitItem = item;
                break;
            }
        }
        if (hitItem) {
            const cx = hitItem.box.x + hitItem.box.w / 2;
            const cy = hitItem.box.y + hitItem.box.h / 2;
            try {
                const res = await api(`/session/${state.sessionId}/layers/lift`, 'POST', { x: Math.floor(cx), y: Math.floor(cy) });
                await refreshImage();
                state.detectedItems = state.detectedItems.filter(i => i !== hitItem);
                selectLayer(res.layer_id);
            } catch (e) { }
            return;
        }
    }


    if (hitLayerId) {
        selectLayer(hitLayerId);
        if (state.activeTool === 'select') {
            state.isDragging = true;
            state.dragMode = 'layer';
            state.dragStart = pos;
            state.dragOffset = { x: 0, y: 0 };
            return;
        }
    } else {
        if (state.activeTool === 'select') state.selectedLayerId = null;
        updateLayersUI();
    }
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
    }
});

dom.canvas.addEventListener('mouseup', async () => {
    if (!state.isDragging) return;
    state.isDragging = false;

    if (state.dragMode === 'layer' && state.selectedLayerId) {
        const { x, y } = state.dragOffset;
        if (x !== 0 || y !== 0) {
            try {
                await api(`/session/${state.sessionId}/layers/${state.selectedLayerId}`, 'PUT', { dx: Math.floor(x), dy: Math.floor(y) });
                await refreshImage();
            } catch (e) {
                alert(e.message);
            }
        }
        state.dragOffset = { x: 0, y: 0 };
        draw();
    }
});

function draw() {
    ctx.clearRect(0, 0, dom.canvas.width, dom.canvas.height);

    // Image
    if (state.currentImageBlob) {
        ctx.drawImage(state.currentImageBlob, 0, 0);
    }

    // Layers
    state.layers.forEach(l => {
        if (l.type === 'image') return;

        let lx = l.x;
        let ly = l.y;
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
            l.width = lw; l.height = lh;
        }

        const isSelected = l.id === state.selectedLayerId;

        if (isSelected) {
            ctx.strokeStyle = '#00f';
            ctx.lineWidth = 2;
            ctx.strokeRect(lx, ly, lw, lh);
            // Handles
            ctx.fillStyle = '#fff';
            ctx.fillRect(lx - 3, ly - 3, 6, 6);
            ctx.fillRect(lx + lw - 3, ly + lh - 3, 6, 6);
        }
    });

    // Detected Items
    state.detectedItems.forEach(item => {
        const { x, y, w, h } = item.box;
        ctx.strokeStyle = '#0f0';
        ctx.lineWidth = 2;
        ctx.strokeRect(x, y, w, h);
    });
}
