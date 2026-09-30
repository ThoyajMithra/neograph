import { useState } from 'react';
import { useApp } from '../../context/AppContext';

export default function Sidebar({ collapsed, setCollapsed }) {
    
    const { docs, selectedDocs, toggleDoc } = useApp();
        

  return (
    <aside className={collapsed ? 'sidebar collapsed' : 'sidebar'}>
      <div className="title" onClick={() => setCollapsed(!collapsed)}>
        {collapsed ? '>' : '⌄ DOCS'}
      </div>

      {!collapsed &&
        docs.map((doc) => (
          <label key={doc} className="row">
            <input
              type="checkbox"
              checked={selectedDocs.includes(doc)}
              onChange={() => toggleDoc(doc)}
            />
            {doc}
          </label>
        ))}
    </aside>
  );
}