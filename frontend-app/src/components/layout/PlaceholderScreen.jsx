import { Icon } from '../Icon';

export function PlaceholderScreen({ title, module }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', gap: 12, color: '#8f9c97' }}>
      <Icon name="layers" size={36} color="#d5ddd9" />
      <div style={{ fontSize: 15, fontWeight: 600, color: '#4a5550' }}>{title}</div>
      <div style={{ fontSize: 12 }}>Módulo {module} — En construcción</div>
    </div>
  );
}
