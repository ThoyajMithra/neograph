import { createContext, useContext, useState, useEffect } from 'react';
import { askBackend,fetchDocs } from '../api/api';

const AppContext = createContext();

export function AppProvider({ children }) {
  // const [docs] = useState(['pdf1.pdf', 'doc1.doc', 'text1.txt', 'md1.md']);
  const [selectedDocs, setSelectedDocs] = useState([]);
  const [messages, setMessages] = useState([]);
  const [docs, setDocs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchDocs().then(setDocs).catch((e) => setError(e.message));
  }, []);
  


  const toggleDoc = (doc) =>
    setSelectedDocs((prev) =>
      prev.includes(doc) ? prev.filter((d) => d !== doc) : [...prev, doc]
    );


  const sendMessage = async (text) => {
    setMessages((prev) => [...prev, {  "*":text }]);
    setLoading(true);
    setError(null);
    try {
      const data = await askBackend(text, selectedDocs);
      setMessages((prev) => [...prev, { 'x': data.answer }]);
      console.log(messages)
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };
    

  return (
    <AppContext.Provider
      value={{ docs, selectedDocs, messages , toggleDoc,setMessages , sendMessage }}
    >
      {children}
    </AppContext.Provider>
  );
}

export const useApp = () => useContext(AppContext);