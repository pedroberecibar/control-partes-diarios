import { Component } from 'react';

export class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, info: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, info) {
    this.setState({ info });
    console.error('[ErrorBoundary]', error, info);
  }

  render() {
    if (!this.state.hasError) return this.props.children;
    const { error, info } = this.state;
    return (
      <div style={{ padding: 24, fontFamily: 'monospace', background: '#1a1a1a', color: '#f8f8f2', height: '100%', overflow: 'auto', boxSizing: 'border-box' }}>
        <div style={{ fontSize: 16, fontWeight: 700, color: '#ff5555', marginBottom: 12 }}>
          Runtime Error — {error?.name}
        </div>
        <pre style={{ background: '#282828', padding: 16, borderRadius: 6, fontSize: 12, color: '#ffb86c', whiteSpace: 'pre-wrap', wordBreak: 'break-all', marginBottom: 16 }}>
          {error?.message}
        </pre>
        <div style={{ fontSize: 13, color: '#8be9fd', marginBottom: 6, fontWeight: 600 }}>Stack Trace:</div>
        <pre style={{ background: '#282828', padding: 16, borderRadius: 6, fontSize: 11, color: '#f8f8f2', whiteSpace: 'pre-wrap', wordBreak: 'break-all', marginBottom: 20 }}>
          {info?.componentStack || error?.stack}
        </pre>
        <button
          onClick={() => { sessionStorage.clear(); localStorage.clear(); window.location.reload(); }}
          style={{ background: '#c0392b', color: 'white', border: 'none', borderRadius: 5, padding: '10px 20px', fontSize: 13, fontWeight: 700, cursor: 'pointer' }}
        >
          Limpiar Sesión y Recargar
        </button>
      </div>
    );
  }
}
