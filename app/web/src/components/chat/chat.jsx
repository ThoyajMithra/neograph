import { useState, useRef, useEffect } from 'react';
import { useApp } from '../../context/AppContext';

export default function Chat() {
  const { messages, sendMessage, loading, error } = useApp();
  const [text, setText] = useState('');
  const [height, setHeight] = useState(200);
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  const send = () => {
    if (!text.trim() || loading) return;
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
      <div className="resizer" onPointerDown={startResize} onPointerMove={resize} />
      <div className="title">CHAT</div>

      <div className="messages">
        {messages.map((m, i) => (
          <div key={i} className={`message ${m.role === 'user' ? 'user' : 'ai'}`}>
            {m.text}
          </div>
        ))}
        {loading && <div className="message ai">Thinking...</div>}
        {error && <div className="message ai">Error: {error}</div>}
        <div ref={bottomRef} />
      </div>

      <input
        value={text}
        placeholder="Question..."
        disabled={loading}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => e.key === 'Enter' && send()}
      />
    </footer>
  );
}