import { useState } from 'react';
import Sidebar from '../sidebar/sidebar.jsx';
import Graph from '../graph/graph.jsx';
import Chat from '../chat/chat.jsx';

export default function AppLayout() {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [pendingMention, setPendingMention] = useState(null);

  return (
    <div className="app">
      <div className="main">
        <Sidebar collapsed={sidebarCollapsed} setCollapsed={setSidebarCollapsed} />
        <Graph />
      </div>
        <Chat pendingMention={pendingMention} setPendingMention={setPendingMention} />
    </div>
  );
}