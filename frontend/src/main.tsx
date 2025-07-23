import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';  // ✅ This fixes the error
import App from './App';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>      {/* ✅ Required for useNavigate() */}
      <App />
    </BrowserRouter>
  </React.StrictMode>
);
