import { useRef } from 'react';
import { useApp } from '../../context/AppContext';

export default function Sidebar({ collapsed, setCollapsed }) {
  const { docs, selectedDocs, toggleDoc, uploadFiles, uploading } = useApp();
  const fileRef = useRef(null);

  const handleFiles = async (e) => {
    // const files = Array.from(e.target.files);
    // console.log("Selected files:");
    
    // files.forEach((file) => {
    //   console.log({
    //     name: file.name,
    //     type: file.type,
    //     size: file.size,
    //   });
    // });
    await uploadFiles(Array.from(e.target.files));
    e.target.value = '';
    
  };

  return (
    <aside className={collapsed ? 'sidebar collapsed' : 'sidebar'}>
      <div className="title" onClick={() => setCollapsed(!collapsed)}>
        {collapsed ? '>' : '⌄ DOCS'}
      </div>

      {!collapsed && (
        <>
          <div className="doc-list">
            {docs.map((doc) => (
              <label key={doc} className="row">
                <input
                  type="checkbox"
                  checked={selectedDocs.includes(doc)}
                  onChange={() => toggleDoc(doc)}
                />
                {doc}
              </label>
            ))}
          </div>

          <input
            ref={fileRef}
            type="file"
            multiple
            hidden
            accept=".pdf,.doc,.docx,.txt,.md,.csv,.xlsx,.pptx"
            onChange={handleFiles}
          />
          
          <button
            className="upload"
            onClick={() => fileRef.current.click()}
            disabled={uploading}
          >
            {uploading ? 'Uploading...' : '+ Upload'}
          </button>
        </>
      )}
    </aside>
  );
}