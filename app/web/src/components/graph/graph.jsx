import { useEffect, useRef, useState } from "react";
import cytoscape from "cytoscape";
import fcose from "cytoscape-fcose";
cytoscape.use(fcose);
import { getOverview, getNode } from "../../api/graph";
import { toElements } from "../../components/graph/elements";

// Color is generated from the type name, so new types get colors automatically.
const typeColor = (type = "") => {
  let h = 0;
  for (const c of type.toUpperCase()) h = (h * 31 + c.charCodeAt(0)) % 360;
  return `hsl(${h}, 60%, 60%)`;
};

const MIN_SIZE = 30;
const MAX_SIZE = 72;

const STYLE = [
  {
    selector: "node",
    style: {
      label: "data(label)",
      "background-color": "data(color)",
      "background-opacity": 0.45,
      "border-color": "data(color)",
      "border-width": 2.5,
      width: "data(size)",
      height: "data(size)",
      color: "#f2f5fa",
      "font-family": "Segoe UI, system-ui, sans-serif",
      "font-size": 16,
      "text-valign": "bottom",
      "text-halign": "center",
      "text-margin-y": 8,
      "text-wrap": "wrap",
      "text-max-width": 120,
      "text-outline-color": "#1e1e1e",
      "text-outline-width": 3,
      "min-zoomed-font-size": 8, // no tiny smudged labels when zoomed far out
    },
  },
  {
    selector: "edge",
    style: {
      width: 1,
      "line-color": "#4a4f5a",
      "curve-style": "bezier",
      color: "#cfd4dc",
      "font-family": "Segoe UI, system-ui, sans-serif",
      "font-size": 12,
      "text-rotation": "autorotate",
      "text-outline-color": "#1e1e1e",
      "text-outline-width": 3,
    },
  },
  {
    selector: "node:selected",
    style: {
      "border-width": 4,
      "border-color": "#ffffff",
      "background-opacity": 0.7,
    },
  },
  // hover: faded everything else, show the hovered node's edge labels
  { selector: ".faded", style: { opacity: 0.15 } },
  {
    selector: "edge.show",
    style: {
      label: "data(label)",
      "line-color": "#8b929e",
      width: 2,
    },
  },
];

const LAYOUT = {
  name: "fcose",
  animate: false,
  randomize: true,
  fit: true,
  padding: 20,
  quality: "proof",
  packComponents: true,
  nodeDimensionsIncludeLabels: true,
  nodeRepulsion: () => 12000,
  idealEdgeLength: () => 80,
  nodeSeparation: 80,
};

export default function Graph() {
  const containerRef = useRef(null);
  const cyRef = useRef(null);
  const [status, setStatus] = useState("loading"); // loading | ready | error
  const [error, setError] = useState("");
  const [selected, setSelected] = useState(null);

  useEffect(() => {
    let cancelled = false;

    async function init() {
      try {
        const { nodes, edges } = await getOverview(100);

        if (cancelled) return;

        const elements = toElements(nodes, edges).map((el) =>
          el.data.type ? { data: { ...el.data, color: typeColor(el.data.type) } } : el
        );

        const cy = cytoscape({
          container: containerRef.current,
          elements,
          style: STYLE,
          minZoom: 0.2,
          maxZoom: 3,
          wheelSensitivity: 0.3,
          pixelRatio: Math.max(2, window.devicePixelRatio || 1), // sharper text
        });

        // size each node by how many connections it has
        const maxDeg = Math.max(1, ...cy.nodes().map((n) => n.degree()));
        cy.nodes().forEach((n) => {
          n.data("size", MIN_SIZE + (n.degree() / maxDeg) * (MAX_SIZE - MIN_SIZE));
        });

        const layout = cy.layout(LAYOUT);
        layout.one("layoutstop", () => {
          cy.zoom({
            level: cy.zoom() * 1.3,
            renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 },
          });
        });
        layout.run();

        // hover: highlight the node's neighborhood, fade the rest
        cy.on("mouseover", "node", (evt) => {
          cy.elements().addClass("faded");
          evt.target.closedNeighborhood().removeClass("faded");
          evt.target.connectedEdges().addClass("show");
        });
        cy.on("mouseout", "node", () => {
          cy.elements().removeClass("faded show");
        });

        cy.on("tap", "node", async (evt) => {
          try {
            setSelected(await getNode(evt.target.id()));
          } catch (e) {
            console.error(e);
          }
        });
        cy.on("tap", (evt) => {
          if (evt.target === cy) setSelected(null);
        });

        cyRef.current = cy;
        setStatus("ready");
      } catch (e) {
        if (!cancelled) {
          setError(e.message);
          setStatus("error");
        }
      }
    }

    init();

    return () => {
      cancelled = true;
      cyRef.current?.destroy();
      cyRef.current = null;
    };
  }, []);

  // keep the canvas correct when the area resizes (e.g. dragging the chat resizer)
  useEffect(() => {
    const ro = new ResizeObserver(() => cyRef.current?.resize());
    ro.observe(containerRef.current);
    return () => ro.disconnect();
  }, []);

  const zoomBy = (factor) => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.zoom({
      level: cy.zoom() * factor,
      renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 },
    });
  };
  const fitAll = () => cyRef.current?.fit(undefined, 20);

  return (
    <section className="graph">
      <div className="graph-canvas" ref={containerRef} />
      <div className="graph-header">
        <span>NEO GRAPH</span>
        {/* <span className="graph-subtitle"> · Visual exploration</span> */}
      </div>

      <div className="graph-controls">
        <button onClick={() => zoomBy(1.25)} title="Zoom in">+</button>
        <button onClick={() => zoomBy(0.8)} title="Zoom out">−</button>
        <button onClick={fitAll} title="Fit all">⤢</button>
      </div>

      {status === "loading" && <div className="graph-msg">Loading graph…</div>}
      {status === "error" && <div className="graph-msg">Failed to load: {error}</div>}

      {selected && (
        <aside className="graph-panel">
          <h3>{selected.label}</h3>
          <p className="graph-type" style={{ color: typeColor(selected.type) }}>
            {selected.type}
          </p>
          <p>{selected.description}</p>
          {selected.aliases.length > 0 && <p>Aliases: {selected.aliases.join(", ")}</p>}
          <p>Appears in {selected.chunkIds.length} chunks</p>
        </aside>
      )}
    </section>
  );
}