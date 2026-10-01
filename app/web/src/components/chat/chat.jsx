import { useState,useRef } from 'react';
import { useApp } from '../../context/AppContext';


export default function Chat() {
  const { messages,selectedDocs,setMessages,sendMessage } = useApp();
  const [text, setText] = useState('');
  const [height, setHeight] = useState(200);
  const fileRef = useRef(null);
  

  const send = () => {
    if (!text.trim()) return;
    sendMessage(text);
    setText('');
  };


  const startResize = (e) => {
    e.preventDefault();
    e.currentTarget.setPointerCapture(e.pointerId);
  };

  const resize = (e) => {
    if (!e.currentTarget.hasPointerCapture(e.pointerId)) return;
    const newHeight = window.innerHeight - e.clientY;
    setHeight(Math.min(Math.max(newHeight, 80), window.innerHeight - 150));
  };

  return (
    <footer className="chat" style={{ height }}>
      <div
        className="resizer"
        onPointerDown={startResize}
        onPointerMove={resize}
      />
      <div className="title">CHAT</div>

      <div className='messages'>
        {messages.map((m, i) => (
          <div key={i} className={`message ${m["x"] ? "ai" : "user"}`}>
            {m["x"] ? "*" + m["x"] : "  " + m["*"]}
          </div>
        ))}
      </div>
      
      <input
        value={text}
        placeholder="Question..."
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => e.key === 'Enter' && send() }
      />
    </footer>
  );
}