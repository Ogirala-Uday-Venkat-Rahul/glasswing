import Chat from "./components/Chat.jsx";

export default function App() {
  return (
    <div className="app">
      <header className="header">
        <h1>Glasswing</h1>
        <p className="tagline">An agent you can see think.</p>
      </header>
      <Chat />
    </div>
  );
}
