document.addEventListener('DOMContentLoaded', function () {
    var container = document.getElementById('graph-canvas');
    if (!container) return;

    var network = null;
    var nodesDataset = new vis.DataSet();
    var edgesDataset = new vis.DataSet();

    var options = {
        nodes: {
            shape: 'box',
            margin: 10,
            font: { size: 14, color: '#fff', face: 'sans-serif' },
            borderWidth: 0,
            shadow: { enabled: true, size: 4, x: 2, y: 2 },
            widthConstraint: { minimum: 120, maximum: 180 },
        },
        edges: {
            arrows: { to: { enabled: true, scaleFactor: 0.8 } },
            color: { color: '#6c757d', highlight: '#0d6efd' },
            width: 2,
            smooth: { type: 'cubicBezier', roundness: 0.4 },
        },
        physics: {
            enabled: false,
        },
        interaction: {
            dragNodes: true,
            dragView: true,
            zoomView: true,
            selectConnectedEdges: false,
        },
        manipulation: {
            enabled: false,
            addEdge: function (edgeData, callback) {
                if (edgeData.from === edgeData.to) return;
                var existing = edgesDataset.get({
                    filter: function (e) {
                        return e.from === edgeData.from && e.to === edgeData.to;
                    },
                });
                if (existing.length > 0) return;
                edgeData.arrows = { to: { enabled: true } };
                callback(edgeData);
            },
        },
    };

    function fitGraphView() {
        if (!network) return;
        try {
            network.fit({ animation: false, padding: 40 });
        } catch (e) { /* ignore */ }
    }

    function collectGraphPayload() {
        if (!network) {
            return { nodes: [], edges: [] };
        }
        var positions = network.getPositions();
        var nodes = [];
        nodesDataset.forEach(function (n) {
            var pos = positions[n.id] || { x: 0, y: 0 };
            nodes.push({ id: n.id, x: pos.x, y: pos.y });
        });
        var edges = [];
        edgesDataset.forEach(function (e) {
            edges.push({ from: e.from, to: e.to });
        });
        return { nodes: nodes, edges: edges };
    }

    function enterAddEdgeMode() {
        if (!network) return;
        network.addEdgeMode();
        showToast('Drag from the prerequisite step to the step that depends on it. Press Esc to cancel.', 'info');
    }

    function loadGraph() {
        fetch(window.GRAPH_DATA_URL)
            .then(function (r) {
                if (!r.ok) throw new Error('Graph data request failed');
                return r.json();
            })
            .then(function (data) {
                nodesDataset.clear();
                edgesDataset.clear();

                (data.nodes || []).forEach(function (n) {
                    nodesDataset.add({
                        id: n.id,
                        label: n.label,
                        x: n.x,
                        y: n.y,
                        color: { background: n.color, border: n.color },
                    });
                });

                (data.edges || []).forEach(function (e) {
                    edgesDataset.add({
                        id: 'dep_' + e.id,
                        from: e.from,
                        to: e.to,
                    });
                });

                network = new vis.Network(container, { nodes: nodesDataset, edges: edgesDataset }, options);

                network.on('doubleClick', function (params) {
                    if (params.nodes.length === 1) {
                        var stepId = params.nodes[0];
                        var planId = window.STEP_DETAIL_BASE_URL.match(/plan\/(\d+)/)[1];
                        window.location.href = '/designer/plan/' + planId + '/step/' + stepId + '/';
                    }
                });

                setTimeout(fitGraphView, 0);
                setTimeout(fitGraphView, 100);
            })
            .catch(function () {
                showToast('Could not load graph data.', 'danger');
            });
    }

    loadGraph();

    var planForm = document.getElementById('plan-update-form');
    var graphPayloadInput = document.getElementById('graph-payload-input');
    if (planForm && graphPayloadInput) {
        planForm.addEventListener('submit', function () {
            try {
                graphPayloadInput.value = JSON.stringify(collectGraphPayload());
            } catch (err) {
                graphPayloadInput.value = '';
            }
        });
    }

    var btnFit = document.getElementById('btn-fit-graph');
    if (btnFit) {
        btnFit.addEventListener('click', function () {
            if (network) network.fit({ animation: true });
        });
    }

    var btnAddDep = document.getElementById('btn-add-dependency');
    if (btnAddDep) {
        btnAddDep.addEventListener('click', function () {
            enterAddEdgeMode();
        });
    }

    document.addEventListener('keydown', function (e) {
        if (e.key === 'e' && !e.ctrlKey && !e.metaKey && document.activeElement.tagName !== 'INPUT' && document.activeElement.tagName !== 'TEXTAREA') {
            enterAddEdgeMode();
        }
        if (e.key === 'Escape') {
            if (network) network.disableEditMode();
        }
        if (e.key === 'Delete' || e.key === 'Backspace') {
            if (document.activeElement.tagName === 'INPUT' || document.activeElement.tagName === 'TEXTAREA') return;
            var sel = network && network.getSelectedEdges();
            if (sel && sel.length > 0) {
                sel.forEach(function (eid) { edgesDataset.remove(eid); });
                showToast('Edge(s) removed. Click Save plan & graph to persist.', 'warning');
            }
        }
    });

    function showToast(message, type) {
        var existing = document.querySelector('.graph-toast');
        if (existing) existing.remove();

        var toast = document.createElement('div');
        toast.className = 'graph-toast alert alert-' + type + ' position-fixed shadow';
        toast.style.cssText = 'bottom:20px;right:20px;z-index:9999;min-width:300px;';
        toast.textContent = message;
        document.body.appendChild(toast);
        setTimeout(function () { toast.remove(); }, 4000);
    }
});
