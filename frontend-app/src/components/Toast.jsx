import { Icon } from './Icon';

const ICON_MAP = { success: 'check-circle', error: 'x-circle', info: 'info', warning: 'alert-triangle' };
const COLOR_MAP = { success: '#1d8348', error: '#c0392b', info: '#1565c0', warning: '#e6910a' };

export function Toast({ toasts, onRemove }) {
  return (
    <div style={{ position: 'fixed', bottom: 24, right: 24, zIndex: 999, display: 'flex', flexDirection: 'column', gap: 8 }}>
      {toasts.map((t) => (
        <div
          key={t.id}
          className="toast"
          style={{
            display: 'flex', alignItems: 'center', gap: 10,
            padding: '10px 14px',
            background: 'white', border: '1px solid #eaeeec',
            borderRadius: 6,
            boxShadow: '0 8px 24px rgba(0,0,0,0.12)',
            fontSize: 12.5, color: '#2f3733', maxWidth: 340, cursor: 'pointer',
          }}
          onClick={() => onRemove(t.id)}
        >
          <Icon
            name={ICON_MAP[t.type] || 'info'}
            size={16}
            color={COLOR_MAP[t.type] || '#1565c0'}
          />
          {t.msg}
        </div>
      ))}
    </div>
  );
}
