from flask import Flask, render_template, request, redirect, url_for, session, send_file
import sqlite3
from datetime import date
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from io import StringIO, BytesIO
import csv

app = Flask(__name__)
app.secret_key = 'tajna_lozinka'

def get_db():
    return sqlite3.connect('baza.db')

@app.route('/')
def index():
    if 'korisnik_id' not in session:
        return redirect(url_for('login'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        lozinka = request.form['lozinka']
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT id, ime, lozinka, uloga FROM korisnici WHERE email = ?", (email,))
        korisnik = c.fetchone()
        conn.close()
        if korisnik and check_password_hash(korisnik[2], lozinka):
            session['korisnik_id'] = korisnik[0]
            session['ime'] = korisnik[1]
            session['uloga'] = korisnik[3]
            return redirect(url_for('index'))
        return render_template('login.html', greska=True)
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/proizvodi')
def proizvodi():
    if 'korisnik_id' not in session:
        return redirect(url_for('login'))
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM proizvodi")
    proizvodi = c.fetchall()
    conn.close()
    return render_template('proizvodi.html', proizvodi=proizvodi)

@app.route('/dodaj_proizvod', methods=['GET', 'POST'])
def dodaj_proizvod():
    if session.get('uloga') != 'admin':
        return redirect(url_for('index'))
    if request.method == 'POST':
        naziv = request.form['naziv']
        cena = float(request.form['cena'])
        kolicina = int(request.form['kolicina'])
        conn = get_db()
        c = conn.cursor()
        c.execute("INSERT INTO proizvodi (naziv, cena, kolicina) VALUES (?, ?, ?)", (naziv, cena, kolicina))
        conn.commit()
        conn.close()
        return redirect(url_for('proizvodi'))
    return render_template('dodaj_proizvod.html')

@app.route('/korisnici')
def korisnici():
    if session.get('uloga') != 'admin':
        return redirect(url_for('index'))
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM korisnici")
    korisnici = c.fetchall()
    conn.close()
    return render_template('korisnici.html', korisnici=korisnici)

@app.route('/porudzbina', methods=['GET', 'POST'])
def porudzbina():
    if 'korisnik_id' not in session:
        return redirect(url_for('login'))
    conn = get_db()
    c = conn.cursor()
    if request.method == 'POST':
        ucenik = request.form['ucenik']
        datum = request.form.get('datum') or '2024-01-01'
        korisnik_id = session['korisnik_id']
        c.execute("INSERT INTO porudzbine (datum, ucenik, korisnik_id) VALUES (?, ?, ?)", (datum, ucenik, korisnik_id))
        porudzbina_id = c.lastrowid
        proizvodi = c.execute("SELECT * FROM proizvodi").fetchall()
        for p in proizvodi:
            kolicina = int(request.form.get(f'kolicina_{p[0]}', 0))
            if kolicina > 0:
                c.execute("INSERT INTO stavke_porudzbine (porudzbina_id, proizvod_id, kolicina, cena_po_jedinici) VALUES (?, ?, ?, ?)",
                          (porudzbina_id, p[0], kolicina, p[2]))
                c.execute("UPDATE proizvodi SET kolicina = kolicina - ? WHERE id = ?", (kolicina, p[0]))
        conn.commit()
        conn.close()
        return redirect(url_for('porudzbine'))
    danas = date.today().isoformat()  # npr. '2025-05-31'
    proizvodi = c.execute("SELECT * FROM proizvodi").fetchall()
    conn.close()
    return render_template("porudzbina.html", proizvodi=proizvodi, danas = danas)

@app.route('/porudzbine')
def porudzbine():
    if 'korisnik_id' not in session:
        return redirect(url_for('login'))
    od = request.args.get('od', '')
    do = request.args.get('do', '')
    ucenik = request.args.get('ucenik', '')
    query = "SELECT p.id, p.datum, p.ucenik, k.ime FROM porudzbine p JOIN korisnici k ON p.korisnik_id = k.id WHERE 1=1"
    params = []
    if od:
        query += " AND p.datum >= ?"
        params.append(od)
    if do:
        query += " AND p.datum <= ?"
        params.append(do)
    if ucenik:
        query += " AND LOWER(p.ucenik) LIKE ?"
        params.append(f"%{ucenik.lower()}%")
    query += " ORDER BY p.datum DESC"
    conn = get_db()
    c = conn.cursor()
    c.execute(query, params)
    porudzbine = c.fetchall()
    conn.close()
    return render_template("porudzbine.html", porudzbine=porudzbine)

@app.route('/dodaj_korisnika', methods=['GET', 'POST'])
def dodaj_korisnika():
    if session.get('uloga') != 'admin':
        return redirect(url_for('index'))
    if request.method == 'POST':
        ime = request.form['ime']
        email = request.form['email']
        lozinka = generate_password_hash(request.form['lozinka'])
        uloga = request.form['uloga']
        conn = get_db()
        c = conn.cursor()
        c.execute("INSERT INTO korisnici (ime, email, lozinka, uloga) VALUES (?, ?, ?, ?)", (ime, email, lozinka, uloga))
        conn.commit()
        conn.close()
        return redirect(url_for('korisnici'))
    return render_template('dodaj_korisnika.html')

@app.route('/obrisi_korisnika/<int:id>')
def obrisi_korisnika(id):
    if session.get('uloga') != 'admin':
        return redirect(url_for('index'))
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM korisnici WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('korisnici'))

@app.route('/obrisi_porudzbinu/<int:porudzbina_id>')
def obrisi_porudzbinu(porudzbina_id):
    if session.get('uloga') != 'admin':
        return redirect(url_for('index'))
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM stavke_porudzbine WHERE porudzbina_id=?", (porudzbina_id,))
    c.execute("DELETE FROM porudzbine WHERE id=?", (porudzbina_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('porudzbine'))

@app.route('/izvestaj_csv')
def izvestaj_csv():
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        SELECT p.naziv, SUM(s.kolicina)
        FROM stavke_porudzbine s
        JOIN proizvodi p ON s.proizvod_id = p.id
        GROUP BY s.proizvod_id
        ORDER BY SUM(s.kolicina) DESC
    """)
    podaci = c.fetchall()
    conn.close()

    # Kreiramo CSV sadržaj kao tekst
    si = StringIO()
    writer = csv.writer(si, delimiter=';')
    writer.writerow(['Proizvod', 'Ukupno naručeno'])
    writer.writerows(podaci)

    # Pretvaramo tekst u bajtove
    output = BytesIO()
    output.write(si.getvalue().encode('utf-8-sig'))
    output.seek(0)

    return send_file(output, mimetype='text/csv', as_attachment=True, download_name='izvestaj.csv')

@app.route('/izvoz_porudzbina')
def izvoz_porudzbina():
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        SELECT p.datum, p.ucenik, k.ime, pr.naziv, s.kolicina
        FROM porudzbine p
        JOIN korisnici k ON p.korisnik_id = k.id
        JOIN stavke_porudzbine s ON s.porudzbina_id = p.id
        JOIN proizvodi pr ON pr.id = s.proizvod_id
        ORDER BY p.datum DESC
    """)
    podaci = c.fetchall()
    conn.close()

    # pišemo CSV kao tekst u StringIO
    si = StringIO()
    writer = csv.writer(si, delimiter=';')
    writer.writerow(['Datum', 'Učenik', 'Radnik', 'Proizvod', 'Količina'])
    writer.writerows(podaci)

    # enkodujemo kao bajtove za BytesIO
    output = BytesIO()
    output.write(si.getvalue().encode('utf-8-sig'))
    output.seek(0)

    return send_file(output, mimetype='text/csv', as_attachment=True, download_name='porudzbine.csv')


@app.route('/admin')
def admin():
    if session.get('uloga') != 'admin':
        return redirect(url_for('index'))
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM korisnici")
    korisnici = c.fetchall()
    c.execute("SELECT * FROM proizvodi")
    proizvodi = c.fetchall()
    c.execute("SELECT COUNT(*) FROM porudzbine")
    ukupno_porudzbina = c.fetchone()[0]
    c.execute("SELECT SUM(s.kolicina * s.cena_po_jedinici) FROM stavke_porudzbine s")
    ukupna_vrednost = c.fetchone()[0] or 0
    c.execute("SELECT p.naziv FROM proizvodi p JOIN stavke_porudzbine s ON s.proizvod_id = p.id GROUP BY p.id ORDER BY SUM(s.kolicina) DESC LIMIT 1")
    top_proizvod = c.fetchone()
    statistika = {
        'ukupno_porudzbina': ukupno_porudzbina,
        'ukupna_vrednost': round(ukupna_vrednost, 2),
        'top_proizvod': top_proizvod[0] if top_proizvod else 'N/A'
    }
    conn.close()
    return render_template("admin_dashboard.html", korisnici=korisnici, proizvodi=proizvodi, statistika=statistika)

@app.route('/izmeni_proizvod/<int:proizvod_id>', methods=['GET', 'POST'])
def izmeni_proizvod(proizvod_id):
    if session.get('uloga') != 'admin':
        return redirect(url_for('index'))
    conn = get_db()
    c = conn.cursor()
    if request.method == 'POST':
        naziv = request.form['naziv']
        cena = float(request.form['cena'])
        kolicina = int(request.form['kolicina'])
        c.execute("UPDATE proizvodi SET naziv=?, cena=?, kolicina=? WHERE id=?", (naziv, cena, kolicina, proizvod_id))
        conn.commit()
        conn.close()
        return redirect(url_for('proizvodi'))
    c.execute("SELECT * FROM proizvodi WHERE id=?", (proizvod_id,))
    proizvod = c.fetchone()
    conn.close()
    return render_template("izmeni_proizvod.html", proizvod=proizvod)

@app.route('/obrisi_proizvod/<int:proizvod_id>')
def obrisi_proizvod(proizvod_id):
    if session.get('uloga') != 'admin':
        return redirect(url_for('index'))
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM proizvodi WHERE id=?", (proizvod_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('proizvodi'))

@app.route('/izmeni_korisnika/<int:id>', methods=['GET', 'POST'])
def izmeni_korisnika(id):
    if session.get('uloga') != 'admin':
        return redirect(url_for('index'))
    conn = get_db()
    c = conn.cursor()
    if request.method == 'POST':
        ime = request.form['ime']
        email = request.form['email']
        uloga = request.form['uloga']
        c.execute("UPDATE korisnici SET ime=?, email=?, uloga=? WHERE id=?", (ime, email, uloga, id))
        conn.commit()
        conn.close()
        return redirect(url_for('korisnici'))
    c.execute("SELECT * FROM korisnici WHERE id=?", (id,))
    korisnik = c.fetchone()
    conn.close()
    return render_template("izmeni_korisnika.html", korisnik=korisnik)

@app.template_filter('formatiraj_broj')
def formatiraj_broj(vrednost):
    try:
        s = f"{float(vrednost):,.2f}"  # dobiješ npr. 1,234,567.89
        s = s.replace(",", "X").replace(".", ",").replace("X", ".")
        return s
    except:
        return vrednost

@app.template_filter('formatiraj_datum')
def formatiraj_datum(datum):
    if isinstance(datum, str):
        # ako je string, pretvori u datetime objekat
        try:
            datum = datetime.fromisoformat(datum)
        except ValueError:
            return datum  # ako ne može da parsira, vrati original
    return datum.strftime('%d.%m.%Y')

if __name__ == '__main__':
    app.run(debug=True, port=5001)