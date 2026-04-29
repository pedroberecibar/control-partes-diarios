import { useRef, useState } from 'react';
import { Icon } from '../components/Icon';

const PREVIEW_ROWS = [
  { sumi: '412881', operario: 'García J.',     fecha: '01/04/2025', med_ret: 'M74829103', med_col: 'M74829200', cod_epec: '1003', ord_nro: 'CE-482301', obs: 'Cambio prog.' },
  { sumi: '518204', operario: 'López M.',      fecha: '01/04/2025', med_ret: 'M61024877', med_col: 'M61025000', cod_epec: '1004', ord_nro: 'CE-517822', obs: '' },
  { sumi: '623771', operario: 'Fernández A.',  fecha: '01/04/2025', med_ret: 'M80112340', med_col: 'M80112500', cod_epec: '1003', ord_nro: '',          obs: 'Sin orden asig' },
  { sumi: '704412', operario: 'García J.',     fecha: '01/04/2025', med_ret: 'M55019980', med_col: 'M55020100', cod_epec: '2001', ord_nro: 'CE-600110', obs: '' },
  { sumi: '811093', operario: 'Torres R.',     fecha: '01/04/2025', med_ret: 'M90231177', med_col: 'M90231300', cod_epec: '1002', ord_nro: 'CE-711209', obs: '' },
];

const ERRORES_VALIDACION = [
  { fila: 3,  col: 'ORD_NRO',     tipo: 'Campo vacío',      msg: 'ORD_NRO es requerido para COD_EPEC 1003/1004. Fila ignorada.' },
  { fila: 14, col: 'FECHA_PARTE', tipo: 'Formato inválido', msg: 'Fecha "1/4/25" no cumple formato DD/MM/YYYY.' },
  { fila: 27, col: 'MEDIDOR_RET', tipo: 'Tipo inválido',    msg: 'Valor "ABC-12345" no es un número de medidor válido.' },
];

export function SubidaArchivos({ onBack }) {
  const [dragOver, setDragOver] = useState(false);
  const [files, setFiles] = useState([]);
  const [contratista, setContratista] = useState('CONECTAR');
  const [step, setStep] = useState('drop'); // drop | preview | validating | result
  const [validProgress, setValidProgress] = useState(0);
  const fileInputRef = useRef();

  function handleDrop(e) {
    e.preventDefault();
    setDragOver(false);
    const droppedFiles = Array.from(e.dataTransfer.files).filter((f) => f.name.match(/\.(xlsx|xls|csv)$/i));
    if (droppedFiles.length) {
      setFiles(droppedFiles);
      setStep('preview');
    }
  }
  function handleFileInput(e) {
    const chosen = Array.from(e.target.files).filter((f) => f.name.match(/\.(xlsx|xls|csv)$/i));
    if (chosen.length) {
      setFiles(chosen);
      setStep('preview');
    }
  }
  function handleValidate() {
    setStep('validating');
    setValidProgress(0);
    const interval = setInterval(() => {
      setValidProgress((p) => {
        if (p >= 100) { clearInterval(interval); setStep('result'); return 100; }
        return p + 8;
      });
    }, 120);
  }

  const sS = {
    root: { padding: 20, overflow: 'auto', height: '100%', boxSizing: 'border-box' },
    pageHeader: { display: 'flex', alignItems: 'center', gap: 12, marginBottom: 18 },
    backBtn: { display: 'inline-flex', alignItems: 'center', gap: 6, padding: '5px 10px', border: '1px solid #d5ddd9', borderRadius: 4, background: 'white', fontSize: 12, fontWeight: 600, color: '#4a5550', cursor: 'pointer' },
    pageTitle: { fontSize: 17, fontWeight: 700, color: '#111614' },
    pageSub: { fontSize: 12, color: '#8f9c97', marginTop: 2 },
    card: { background: 'white', border: '1px solid #eaeeec', borderRadius: 6, overflow: 'hidden', boxShadow: '0 1px 3px rgba(0,0,0,0.05)', marginBottom: 16 },
    cardHeader: { padding: '10px 16px', borderBottom: '1px solid #eaeeec', background: '#fafcfb', display: 'flex', alignItems: 'center', gap: 8 },
    cardTitle: { fontSize: 12, fontWeight: 700, color: '#2f3733', flex: 1 },
    cardBody: { padding: 16 },
    dropZone: {
      border: `2px dashed ${dragOver ? '#124e2f' : '#d5ddd9'}`,
      borderRadius: 6,
      padding: '40px 24px',
      textAlign: 'center',
      background: dragOver ? '#edf5f0' : '#fafcfb',
      transition: 'all 0.15s',
      cursor: 'pointer',
    },
    dropIcon: { marginBottom: 12 },
    dropTitle: { fontSize: 14, fontWeight: 600, color: dragOver ? '#124e2f' : '#4a5550', marginBottom: 6 },
    dropSub: { fontSize: 12, color: '#8f9c97' },
    selectorRow: { display: 'flex', gap: 10, alignItems: 'center', marginBottom: 16 },
    selectorLabel: { fontSize: 12.5, fontWeight: 600, color: '#2f3733', minWidth: 80 },
    selectorBtns: { display: 'flex', gap: 6 },
    selectorBtn: { padding: '6px 14px', border: '1px solid #d5ddd9', borderRadius: 4, fontSize: 12, fontWeight: 600, cursor: 'pointer', transition: 'all 0.12s', color: '#4a5550', background: 'white' },
    selectorBtnActive: { background: '#124e2f', color: 'white', borderColor: '#124e2f' },
    table: { width: '100%', borderCollapse: 'collapse', fontSize: 11.5 },
    th: { padding: '7px 10px', textAlign: 'left', background: '#124e2f', color: 'white', fontWeight: 600, fontSize: 10.5, letterSpacing: '0.04em', whiteSpace: 'nowrap' },
    td: { padding: '6px 10px', borderBottom: '1px solid #f0f3f1', color: '#2f3733', whiteSpace: 'nowrap', fontFamily: "'JetBrains Mono', monospace" },
    fileChip: { display: 'inline-flex', alignItems: 'center', gap: 8, padding: '6px 12px', background: '#edf5f0', border: '1px solid #a8d9c0', borderRadius: 4, fontSize: 12, color: '#124e2f', fontWeight: 500 },
    progressBar: { height: 6, background: '#eaeeec', borderRadius: 3, overflow: 'hidden', marginTop: 8 },
    progressFill: { height: '100%', background: '#124e2f', borderRadius: 3, transition: 'width 0.12s' },
    errorRow: { display: 'flex', gap: 10, padding: '8px 0', borderBottom: '1px solid #fde8e8', alignItems: 'flex-start' },
    btnPrimary: { display: 'inline-flex', alignItems: 'center', gap: 6, padding: '8px 18px', border: 'none', borderRadius: 4, background: '#124e2f', fontSize: 12.5, fontWeight: 600, color: 'white', cursor: 'pointer' },
    btnSecondary: { display: 'inline-flex', alignItems: 'center', gap: 6, padding: '8px 14px', border: '1px solid #d5ddd9', borderRadius: 4, background: 'white', fontSize: 12.5, fontWeight: 600, color: '#4a5550', cursor: 'pointer' },
  };

  return (
    <div style={sS.root}>
      <div style={sS.pageHeader}>
        <button style={sS.backBtn} onClick={onBack}>
          <Icon name="arrow-left" size={13} /> Volver
        </button>
        <div>
          <div style={sS.pageTitle}>Subir Archivos de Partes</div>
          <div style={sS.pageSub}>Módulo A — Ingesta por Drag & Drop</div>
        </div>
      </div>

      {step === 'drop' && (
        <div style={sS.card}>
          <div style={sS.cardBody}>
            <div style={sS.selectorRow}>
              <span style={sS.selectorLabel}>Contratista</span>
              <div style={sS.selectorBtns}>
                {['CONECTAR', 'COOPLYF'].map((c) => (
                  <button
                    key={c}
                    style={{ ...sS.selectorBtn, ...(contratista === c ? sS.selectorBtnActive : {}) }}
                    onClick={() => setContratista(c)}
                  >
                    {c}
                  </button>
                ))}
              </div>
            </div>
            <div
              style={sS.dropZone}
              onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
              onDragLeave={() => setDragOver(false)}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".xlsx,.xls,.csv"
                multiple
                style={{ display: 'none' }}
                onChange={handleFileInput}
              />
              <div style={sS.dropIcon}>
                <Icon name="file-up" size={36} color={dragOver ? '#124e2f' : '#b5bfbb'} />
              </div>
              <div style={sS.dropTitle}>
                {dragOver ? 'Soltar archivos aquí' : 'Arrastrá archivos o hacé click para seleccionar'}
              </div>
              <div style={sS.dropSub}>.xlsx · .xls · .csv · Hasta 50 MB por archivo · Múltiples archivos permitidos</div>
            </div>
          </div>
        </div>
      )}

      {step === 'preview' && (
        <>
          <div style={sS.card}>
            <div style={sS.cardHeader}>
              <Icon name="file-text" size={14} color="#6b7772" />
              <span style={sS.cardTitle}>Archivos seleccionados</span>
              <button style={{ ...sS.btnSecondary, fontSize: 11 }} onClick={() => setStep('drop')}>Cambiar</button>
            </div>
            <div style={sS.cardBody}>
              <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
                {files.map((f, i) => (
                  <div key={i} style={sS.fileChip}>
                    <Icon name="file-text" size={13} color="#124e2f" />
                    {f.name}
                    <span style={{ color: '#8f9c97', fontWeight: 400, fontSize: 11 }}>({(f.size / 1024).toFixed(0)} KB)</span>
                  </div>
                ))}
                {files.length === 0 && (
                  <div style={sS.fileChip}>
                    <Icon name="file-text" size={13} color="#124e2f" />
                    CONECTAR_Partes_Abril_W1.xlsx
                    <span style={{ color: '#8f9c97', fontWeight: 400, fontSize: 11 }}>(218 KB)</span>
                  </div>
                )}
              </div>
              <div style={{ ...sS.selectorRow, marginBottom: 0 }}>
                <span style={sS.selectorLabel}>Contratista</span>
                <div style={sS.selectorBtns}>
                  {['CONECTAR', 'COOPLYF'].map((c) => (
                    <button
                      key={c}
                      style={{ ...sS.selectorBtn, ...(contratista === c ? sS.selectorBtnActive : {}) }}
                      onClick={() => setContratista(c)}
                    >
                      {c}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>

          <div style={sS.card}>
            <div style={sS.cardHeader}>
              <Icon name="eye" size={14} color="#6b7772" />
              <span style={sS.cardTitle}>Vista previa — primeras 5 filas</span>
              <span style={{ fontSize: 10.5, color: '#8f9c97' }}>Solo lectura</span>
            </div>
            <div style={{ overflowX: 'auto' }}>
              <table style={sS.table}>
                <thead>
                  <tr>
                    {['SUMINISTRO', 'OPERARIO', 'FECHA_PARTE', 'MED_RETIRADO', 'MED_COLOCADO', 'COD_EPEC', 'ORD_NRO', 'OBS_APP'].map((h) => (
                      <th key={h} style={sS.th}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {PREVIEW_ROWS.map((r, i) => (
                    <tr key={i} style={{ background: i % 2 === 0 ? 'white' : '#fafcfb' }}>
                      <td style={sS.td}>{r.sumi}</td>
                      <td style={{ ...sS.td, fontFamily: 'inherit' }}>{r.operario}</td>
                      <td style={sS.td}>{r.fecha}</td>
                      <td style={sS.td}>{r.med_ret}</td>
                      <td style={sS.td}>{r.med_col}</td>
                      <td style={sS.td}>{r.cod_epec}</td>
                      <td style={{ ...sS.td, color: r.ord_nro ? '#2f3733' : '#c0392b', fontWeight: r.ord_nro ? 400 : 600 }}>
                        {r.ord_nro || '(vacío)'}
                      </td>
                      <td style={{ ...sS.td, fontFamily: 'inherit' }}>{r.obs || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
            <button style={sS.btnSecondary} onClick={() => { setFiles([]); setStep('drop'); }}>
              Cancelar
            </button>
            <button style={sS.btnPrimary} onClick={handleValidate}>
              <Icon name="check-circle" size={14} /> Validar y Subir
            </button>
          </div>
        </>
      )}

      {step === 'validating' && (
        <div style={sS.card}>
          <div style={sS.cardBody}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
              <Icon name="loader" size={20} color="#124e2f" />
              <div>
                <div style={{ fontSize: 14, fontWeight: 600, color: '#2f3733' }}>Validando archivo…</div>
                <div style={{ fontSize: 11.5, color: '#8f9c97', marginTop: 2 }}>
                  Verificando esquema, tipos y reglas de negocio
                </div>
              </div>
              <span style={{ marginLeft: 'auto', fontFamily: "'JetBrains Mono', monospace", fontSize: 13, fontWeight: 600, color: '#124e2f' }}>
                {validProgress}%
              </span>
            </div>
            <div style={sS.progressBar}>
              <div style={{ ...sS.progressFill, width: `${validProgress}%` }} />
            </div>
            <div style={{ marginTop: 12, fontSize: 11.5, color: '#8f9c97' }}>
              {validProgress < 30
                ? 'Leyendo estructura del archivo…'
                : validProgress < 60
                ? 'Validando tipos y formatos…'
                : validProgress < 90
                ? 'Verificando reglas de negocio…'
                : 'Finalizando…'}
            </div>
          </div>
        </div>
      )}

      {step === 'result' && (
        <>
          <div style={{ ...sS.card, border: '1px solid #a8d9c0' }}>
            <div style={{ ...sS.cardHeader, background: '#edf5f0', borderBottom: '1px solid #a8d9c0' }}>
              <Icon name="check-circle" size={14} color="#1d8348" />
              <span style={{ ...sS.cardTitle, color: '#155a2e' }}>Validación completada — 3 advertencias</span>
            </div>
            <div style={sS.cardBody}>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 12 }}>
                {[['Filas leídas', '312'], ['OK', '309'], ['Advertencias', '3'], ['Errores fatales', '0']].map(([l, v]) => (
                  <div key={l} style={{ textAlign: 'center' }}>
                    <div style={{ fontSize: 20, fontWeight: 700, color: l === 'Errores fatales' ? '#8f9c97' : l === 'Advertencias' ? '#e6910a' : '#155a2e' }}>
                      {v}
                    </div>
                    <div style={{ fontSize: 10.5, color: '#8f9c97', marginTop: 2 }}>{l}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div style={sS.card}>
            <div style={sS.cardHeader}>
              <Icon name="alert-triangle" size={14} color="#e6910a" />
              <span style={sS.cardTitle}>Advertencias detectadas (no bloquean)</span>
            </div>
            <div style={sS.cardBody}>
              {ERRORES_VALIDACION.map((err, i) => (
                <div key={i} style={sS.errorRow}>
                  <div style={{ padding: '3px 7px', borderRadius: 3, background: '#fde8e8', color: '#7a1c1c', fontSize: 10.5, fontWeight: 700, fontFamily: "'JetBrains Mono', monospace", flexShrink: 0 }}>
                    Fila {err.fila}
                  </div>
                  <div style={{ padding: '3px 7px', borderRadius: 3, background: '#fff3cd', color: '#7a4a00', fontSize: 10.5, fontWeight: 600, flexShrink: 0 }}>
                    {err.tipo}
                  </div>
                  <div style={{ padding: '3px 7px', borderRadius: 3, background: '#dbeafe', color: '#0d4272', fontSize: 10.5, fontWeight: 600, fontFamily: "'JetBrains Mono', monospace", flexShrink: 0 }}>
                    {err.col}
                  </div>
                  <div style={{ fontSize: 12, color: '#4a5550', flex: 1 }}>{err.msg}</div>
                </div>
              ))}
            </div>
          </div>

          <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
            <button style={sS.btnSecondary} onClick={() => { setFiles([]); setStep('drop'); }}>
              Descargar Excel con marcas
            </button>
            <button style={sS.btnPrimary} onClick={() => { setStep('drop'); setFiles([]); onBack(); }}>
              <Icon name="send" size={14} /> Enviar al Pipeline
            </button>
          </div>
        </>
      )}
    </div>
  );
}
