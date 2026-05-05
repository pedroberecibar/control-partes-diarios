import sqlite3
conn = sqlite3.connect('data/db/webapp_pd.db')
print('parte', conn.execute('SELECT p.id, COUNT(i.id) FROM partes_diarios_procesados p JOIN parte_imagenes i ON p.id = i.parte_procesado_id GROUP BY p.id LIMIT 1').fetchone())
