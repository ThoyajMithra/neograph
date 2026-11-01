import { useState, useRef, useEffect } from 'react';

const options = [
  { rid: 0, label: 'general' },
  { rid: 1, label: 'reasoning' },
  { rid: 2, label: 'concept' },
];

export default function Dropdown() {
  const [open, setOpen] = useState(false);
  const [selected, setSelected] = useState(options[0]);
  const ref = useRef(null);

  useEffect(() => {
    function onClick(e) {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    }
    function onKey(e) {
      if (e.key === 'Escape') setOpen(false);
    }
    document.addEventListener('mousedown', onClick);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onClick);
      document.removeEventListener('keydown', onKey);
    };
  }, []);

  async function changerid(o) {
    const prev = selected;
    setOpen(false);
    setSelected(o);
    try {
      const res = await fetch(`/api/changetype?rid=${o.rid}`, { method: 'POST' });
      if (!res.ok) throw new Error();
      return res.json();
    } catch {
      setSelected(prev);
    }
  }

  return (
    <div className="dropdown" ref={ref}>
      <button className="dropdown-btn" onClick={() => setOpen(!open)}>
        <span className="dropdown-label">Menu</span>
        <span className="dropdown-value">{selected.label}</span>
        <span className={`dropdown-caret ${open ? 'open' : ''}`}>▾</span>
      </button>
      {open && (
        <div className="dropdown-menu">
          {options.map((o) => (
            <button
              key={o.rid}
              className={o.rid === selected.rid ? 'active' : ''}
              onClick={() => changerid(o)}
            >
              {o.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}