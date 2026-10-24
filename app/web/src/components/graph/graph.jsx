import { useEffect, useRef, useState } from "react";
import cytoscape from "cytoscape";
import { getOverview, getNode } from "../../api/graph";
import { toElements } from "../../components/graph/elements";

// Colors by node type. Change these to taste; unknown types fall back to gray.
const TYPE_COLORS = {
  PERSON: "#e8a33d",
  CONCEPT: "#3fc1d1",
  TECHNOLOGY: "#2fb8a6",
  ORGANIZATION: "#a78bfa",
  EVENT: "#e5534b",
  PRODUCT: "#b9a4f5",
};
const typeColor = (type = "") => TYPE_COLORS[type] || "#8b929e";
const STYLE = [
  {
    selector: "node",
    style: {
      label: "data(label)",
      "background-color": "data(color)",
      "background-opacity": 0.3,
      "border-color": "data(color)",
      "border-width": 2,
      width: 64,
      height: 64,
      color: "#e6edf7",
      "font-size": 24,
      "font-weight": 600,
      "font-family": "Arial, sans-serif",
      "text-valign": "bottom",
      "text-halign": "center",
      // "text-margin-y": 9,
      // "text-wrap": "wrap",
      "text-max-width": 120,
      "text-background-color": "#0b0e14",
      "text-background-opacity": 0.3,
      "text-background-padding": 3,
    },
  },
  {
    selector: "edge",
    style: {
      width: 1.5,
      "line-color": "#414b5d",
      "line-opacity": 0.9,
      "curve-style": "bezier",
      label: "data(label)",
      color: "#aab4c5",
      "font-size": 18,
      "text-rotation": "autorotate",
      "text-background-color": "#0b0e14",
      "text-background-opacity": 0.95,
      // "text-background-padding": 3,
    },
  },
  {
    selector: "node:selected",
    style: {
      "border-width": 4,
      "border-color": "#ffffff",
      "background-opacity": 0.65,
    },
  },
];

const LAYOUT = {
  name: "cose",
  animate: false,
  fit: true,
  padding: 30,
  randomize: true,
  nodeDimensionsIncludeLabels: true,
  nodeRepulsion: () => 50000,
  idealEdgeLength: () => 140,
  edgeElasticity: () => 80,
  gravity: 0.5,
  numIter: 1000,
  componentSpacing: 100,
  nodeOverlap: 30,
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
          layout: LAYOUT,
          style: STYLE,
          minZoom: 0.2,
          maxZoom: 3,
          wheelSensitivity: 0.3,
        });
        // console.log("nodes:", cy.nodes().length, "edges:", cy.edges().length, "size:", containerRef.current.offsetWidth, containerRef.current.offsetHeight);

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
        cy.resize();
        cy.fit(undefined, 40);

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

  const zoomBy = (factor) => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.zoom({
      level: cy.zoom() * factor,
      renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 },
    });
  };
  const fitAll = () => cyRef.current?.fit(undefined, 40);

  return (
    <section className="graph">
      <div
        className="graph-canvas"
        ref={containerRef}
        style={{ flex: 1, minWidth: 0, height: "75vh", minHeight: 500 }}
      />

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