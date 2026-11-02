from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from datetime import datetime
import os
from werkzeug.utils import secure_filename
import uuid
import logging
import secrets
from functools import wraps

app = Flask(__name__)
   
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-only-change-me')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///ecommerce.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False


UPLOAD_FOLDER = os.path.join(app.root_path, 'static', 'images')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif','webp'}
MAX_FILE_SIZE = 5 * 1024 * 1024  


db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'connexion'
login_manager.login_message = 'Veuillez vous connecter pour accéder à cette page.'



def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_uploaded_image(file):
    if file and allowed_file(file.filename):
        
        filename = secure_filename(file.filename)
        name, ext = os.path.splitext(filename)
        unique_filename = f"{uuid.uuid4().hex}{ext}"
        
       
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        filepath = os.path.join(UPLOAD_FOLDER, unique_filename)
        file.save(filepath)
        
        return unique_filename
    return None

def delete_image(filename):
    if filename:
        try:
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            if os.path.exists(filepath):
                os.remove(filepath)
        except Exception as e:
            print(f"Erreur lors de la suppression de l'image {filename}: {e}")

def setup_logging():
    
    if not os.path.exists('logs'):
        os.makedirs('logs')
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('logs/app.log'),
            logging.StreamHandler()
        ]
    )
    
    user_logger = logging.getLogger('user_actions')
    user_handler = logging.FileHandler('logs/user_actions.log')
    user_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
    user_logger.addHandler(user_handler)
    user_logger.setLevel(logging.INFO)
    
    return user_logger


user_logger = setup_logging()


def log_user_action(action, user_info=None, extra_data=None):
    log_data = {
        'action': action,
        'ip': request.remote_addr if request else 'Unknown',
        'timestamp': datetime.now().isoformat()
    }
    
    if user_info:
        log_data['user'] = user_info
    if extra_data:
        log_data.update(extra_data)
    
    user_logger.info(f"USER_ACTION: {log_data}")
    
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.est_admin:
            flash('Accès non autorisé. Seuls les administrateurs peuvent accéder à cette page.', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    mot_de_passe = db.Column(db.String(60), nullable=False)
    est_admin = db.Column(db.Boolean, default=False)
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)

   
    commandes = db.relationship('Commande', backref='utilisateur', lazy=True)
    panier = db.relationship('PanierItem', backref='utilisateur', lazy=True)

class Produit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    prix = db.Column(db.Float)
    image = db.Column(db.String(200))
    categorie = db.Column(db.String(100))
    stock = db.Column(db.Integer, default=0)
    est_nouveaute = db.Column(db.Boolean, default=False)
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)

class PanierItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    produit_id = db.Column(db.Integer, db.ForeignKey('produit.id'), nullable=False)
    quantite = db.Column(db.Integer, default=1)
    date_ajout = db.Column(db.DateTime, default=datetime.utcnow)
    
    produit = db.relationship('Produit', backref='items_panier')

class Commande(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    total = db.Column(db.Float, nullable=False)
    statut = db.Column(db.String(50), default='En attente')
    date_commande = db.Column(db.DateTime, default=datetime.utcnow)
    adresse_livraison = db.Column(db.Text)
    
    items = db.relationship('CommandeItem', backref='commande', lazy=True)

class CommandeItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    commande_id = db.Column(db.Integer, db.ForeignKey('commande.id'), nullable=False)
    produit_id = db.Column(db.Integer, db.ForeignKey('produit.id'), nullable=False)
    quantite = db.Column(db.Integer, nullable=False)
    prix_unitaire = db.Column(db.Float, nullable=False)
    
    produit = db.relationship('Produit')

class Newsletter(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    date_inscription = db.Column(db.DateTime, default=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def get_panier_count():
    if current_user.is_authenticated:
        return PanierItem.query.filter_by(user_id=current_user.id).count()
    return 0

@app.context_processor
def inject_panier_count():
    return dict(panier_count=get_panier_count())

@app.context_processor
def inject_admin_status():
    return dict(
        is_admin=current_user.is_authenticated and current_user.est_admin
    )


@app.route('/')
def index():
    produits_nouveautes = Produit.query.filter_by(est_nouveaute=True).limit(8).all()
    return render_template('index.html', produits_nouveautes=produits_nouveautes)

@app.route('/inscription', methods=['GET', 'POST'])
def inscription():
    if request.method == 'POST':
        nom = request.form['nom']
        email = request.form['email']
        mot_de_passe = request.form['mot_de_passe']
        
        log_user_action('REGISTRATION_ATTEMPT', {'email': email, 'nom': nom})
        
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            log_user_action('REGISTRATION_FAILED', {'email': email}, {'reason': 'Email already exists'})
            flash('Cet email est déjà utilisé.', 'danger')
            return render_template('inscription.html')
        
        try:
            hashed_password = bcrypt.generate_password_hash(mot_de_passe).decode('utf-8')
            user = User(nom=nom, email=email, mot_de_passe=hashed_password)
            db.session.add(user)
            db.session.commit()
            
            log_user_action('REGISTRATION_SUCCESS', {'email': email, 'nom': nom}, {'user_id': user.id})
            flash('Compte créé avec succès! Vous pouvez maintenant vous connecter.', 'success')
            return redirect(url_for('connexion'))
            
        except Exception as e:
            db.session.rollback()
            log_user_action('REGISTRATION_ERROR', {'email': email}, {'error': str(e)})
            flash('Erreur lors de la création du compte.', 'danger')
    
    return render_template('inscription.html')

@app.route('/connexion', methods=['GET', 'POST'])
def connexion():
    if request.method == 'POST':
        email = request.form['email']
        mot_de_passe = request.form['mot_de_passe']
        
        log_user_action('LOGIN_ATTEMPT', {'email': email})
        
        user = User.query.filter_by(email=email).first()
        
        if user and bcrypt.check_password_hash(user.mot_de_passe, mot_de_passe):
            login_user(user)
            log_user_action('LOGIN_SUCCESS', {'email': email, 'nom': user.nom}, {'user_id': user.id})
            flash('Connexion réussie!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('index'))
        else:
            log_user_action('LOGIN_FAILED', {'email': email}, {'reason': 'Invalid credentials'})
            flash('Email ou mot de passe incorrect.', 'danger')
    
    return render_template('connexion.html')

@app.route('/deconnexion')
@login_required
def deconnexion():
    logout_user()
    flash('Vous avez été déconnecté.', 'info')
    return redirect(url_for('index')) 

@app.route('/produit/<int:id>')
def produit_detail(id):
    produit = Produit.query.get_or_404(id)
    # Produits similaires non yet
    produits_similaires = Produit.query.filter(
        Produit.categorie == produit.categorie,
        Produit.id != produit.id
    ).limit(4).all()
    
    return render_template('produit_detail.html', produit=produit, produits_similaires=produits_similaires)

@app.route('/boites-artisanales')
def boites_artisanales():
    produits = Produit.query.filter_by(categorie='boites_artisanales').all()
    return render_template('boites_artisanales.html', produits=produits)

@app.route('/art-de-la-table')
def art_de_la_table():
    produits = Produit.query.filter_by(categorie='art_de_la_table').all()
    return render_template('art_de_la_table.html', produits=produits)

@app.route('/jeux-traditionnels')
def jeux_traditionnels():
    produits = Produit.query.filter_by(categorie='jeux_traditionnels').all()
    return render_template('jeux_traditionnels.html', produits=produits)

@app.route('/nos-artisans')
def nos_artisans():
    return render_template('nos_artisans.html')



@app.route('/panier')
@login_required
def panier():
    items_panier = PanierItem.query.filter_by(user_id=current_user.id).all()
    total = sum(item.produit.prix * item.quantite for item in items_panier if item.produit and item.produit.prix)
    return render_template('panier.html', items_panier=items_panier, total=total)

@app.route('/ajouter-au-panier/<int:produit_id>', methods=['POST'])
@login_required
def ajouter_au_panier(produit_id):
    produit = Produit.query.get_or_404(produit_id)
    quantite = int(request.form.get('quantite', 1))
    
    
    if quantite > produit.stock:
        flash(f'Stock insuffisant. Stock disponible: {produit.stock}', 'error')
        return redirect(request.referrer or url_for('index'))
    
    item_existant = PanierItem.query.filter_by(
        user_id=current_user.id, 
        produit_id=produit_id
    ).first()
    
    if item_existant:
        nouvelle_quantite = item_existant.quantite + quantite
        if nouvelle_quantite > produit.stock:
            flash(f'Stock insuffisant. Quantité maximale disponible: {produit.stock}', 'error')
            return redirect(request.referrer or url_for('index'))
        item_existant.quantite = nouvelle_quantite
    else:
        nouveau_item = PanierItem(
            user_id=current_user.id,
            produit_id=produit_id,
            quantite=quantite
        )
        db.session.add(nouveau_item)
    
    try:
        db.session.commit()
        flash(f'{produit.nom} ajouté au panier!', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Erreur lors de l\'ajout au panier.', 'error')
    
    return redirect(request.referrer or url_for('index'))

@app.route('/mettre-a-jour-quantite/<int:item_id>', methods=['POST'])
@login_required
def mettre_a_jour_quantite(item_id):
    item = PanierItem.query.get_or_404(item_id)
    
    if item.user_id != current_user.id:
        flash('Accès non autorisé.', 'error')
        return redirect(url_for('panier'))
    
    try:
        nouvelle_quantite = int(request.form['quantite'])
        if nouvelle_quantite < 1:
            flash('La quantité doit être au moins 1.', 'error')
        elif nouvelle_quantite > item.produit.stock:
            flash(f'Stock insuffisant. Stock disponible: {item.produit.stock}', 'error')
        else:
            item.quantite = nouvelle_quantite
            db.session.commit()
            flash('Quantité mise à jour avec succès.', 'success')
    except (ValueError, TypeError):
        flash('Quantité invalide.', 'error')
    except Exception as e:
        db.session.rollback()
        flash('Erreur lors de la mise à jour.', 'error')
    
    return redirect(url_for('panier'))

@app.route('/supprimer-du-panier/<int:item_id>')
@login_required
def supprimer_du_panier(item_id):
    item = PanierItem.query.get_or_404(item_id)
    if item.user_id == current_user.id:
        try:
            db.session.delete(item)
            db.session.commit()
            flash('Article supprimé du panier.', 'info')
        except Exception as e:
            db.session.rollback()
            flash('Erreur lors de la suppression.', 'error')
    else:
        flash('Accès non autorisé.', 'error')
    
    return redirect(url_for('panier'))


@app.route('/checkout', methods=['GET', 'POST'])
@login_required
def checkout():
    items_panier = PanierItem.query.filter_by(user_id=current_user.id).all()
    
    if not items_panier:
        flash('Votre panier est vide.', 'info')
        return redirect(url_for('panier'))
    
    total = sum(item.produit.prix * item.quantite for item in items_panier if item.produit and item.produit.prix)
    
    if request.method == 'POST':
        try:
            
            prenom = request.form.get('prenom', '').strip()
            nom = request.form.get('nom', '').strip()
            email = request.form.get('email', '').strip()
            telephone = request.form.get('telephone', '').strip()
            adresse = request.form.get('adresse', '').strip()
            ville = request.form.get('ville', '').strip()
            code_postal = request.form.get('code_postal', '').strip()
            methode_paiement = request.form.get('methode_paiement', 'cash')
            notes = request.form.get('notes', '').strip()
            
            if not all([prenom, nom, email, telephone, adresse, ville]):
                flash('Veuillez remplir tous les champs obligatoires.', 'error')
                return render_template('checkout.html', items_panier=items_panier, total=total)
            
            
            import re
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, email):
                flash('Veuillez entrer une adresse email valide.', 'error')
                return render_template('checkout.html', items_panier=items_panier, total=total)
            
          
            for item in items_panier:
                if item.quantite > item.produit.stock:
                    flash(f'Stock insuffisant pour {item.produit.nom}. Stock disponible: {item.produit.stock}', 'error')
                    return render_template('checkout.html', items_panier=items_panier, total=total)
            
            adresse_complete = f"{prenom} {nom}\n{adresse}\n{ville}"
            if code_postal:
                adresse_complete += f" {code_postal}"
            if notes:
                adresse_complete += f"\nNotes: {notes}"
            
            nouvelle_commande = Commande(
                user_id=current_user.id,
                total=total,
                statut='En attente',
                adresse_livraison=adresse_complete
            )
            
            db.session.add(nouvelle_commande)
            db.session.flush()  
            
            for item in items_panier:
                commande_item = CommandeItem(
                    commande_id=nouvelle_commande.id,
                    produit_id=item.produit_id,
                    quantite=item.quantite,
                    prix_unitaire=item.produit.prix
                )
                db.session.add(commande_item)
                
            
                item.produit.stock -= item.quantite
            
           
            PanierItem.query.filter_by(user_id=current_user.id).delete()
            
            
            db.session.commit()
            
            # Logs
            log_user_action('ORDER_CREATED', 
                          {'user_id': current_user.id, 'email': current_user.email}, 
                          {'order_id': nouvelle_commande.id, 'total': total, 'payment_method': methode_paiement})
            
           
            if methode_paiement == 'cash':
                message_paiement = "Vous paierez à la livraison."
            elif methode_paiement == 'card':
                message_paiement = "Procédez au paiement par carte bancaire."
            else:  
                message_paiement = "Vous recevrez les détails pour le virement bancaire par email."
            
            flash(f'Commande #{nouvelle_commande.id} créée avec succès! {message_paiement}', 'success')
            
         
            return redirect(url_for('confirmation_commande', commande_id=nouvelle_commande.id))
            
        except Exception as e:
            db.session.rollback()
            log_user_action('ORDER_ERROR', 
                          {'user_id': current_user.id}, 
                          {'error': str(e)})
            flash('Erreur lors du traitement de votre commande. Veuillez réessayer.', 'error')
            return render_template('checkout.html', items_panier=items_panier, total=total)
    
   
    return render_template('checkout.html', items_panier=items_panier, total=total)



@app.route('/confirmation/<int:commande_id>')
@login_required
def confirmation_commande(commande_id):
    commande = Commande.query.filter_by(id=commande_id, user_id=current_user.id).first_or_404()
    return render_template('confirmation.html', commande=commande)


@app.route('/newsletter', methods=['POST'])# non
def newsletter():
    email = request.form['email']
   
    existing_newsletter = Newsletter.query.filter_by(email=email).first()
    if not existing_newsletter:
        nouvelle_inscription = Newsletter(email=email)
        db.session.add(nouvelle_inscription)
        db.session.commit()
        flash('Inscription à la newsletter réussie!', 'success')
    else:
        flash('Cet email est déjà inscrit à la newsletter.', 'info')
    
    return redirect(request.referrer or url_for('index'))



def ajouter_produits_jeux():
   
    
    if not Produit.query.filter_by(categorie='jeux_traditionnels').first():
        produits_jeux = [
            Produit(
                nom="Échiquier en bois de Thuya",
                description="Échiquier artisanal en bois de Thuya avec finitions traditionnelles",
                prix=500.0,
                image="j.webp",
                categorie="jeux_traditionnels",
                stock=5,
                est_nouveaute=True
            ),
            Produit(
                nom="Jeu solitaire en bois de thuya",
                description="Jeu de solitaire traditionnel en bois de thuya",
                prix=460.0,
                image="jj.jpg",
                categorie="jeux_traditionnels",
                stock=8,
                est_nouveaute=True
            ),
            Produit(
                nom="Jeu de domino et dés artisanale en bois",
                description="Set complet de dominos et dés en bois artisanal",
                prix=600.0,
                image="kk.jpg",
                categorie="jeux_traditionnels",
                stock=6,
                est_nouveaute=True
            ),
            Produit(
                nom="Boîte de jeu d'échecs artisanale",
                description="Boîte complète avec échiquier et pièces artisanales",
                prix=730.0,
                image="jeee.jpeg",
                categorie="jeux_traditionnels",
                stock=4,
                est_nouveaute=True
            ),
            Produit(
                nom="Boîte à bois en racine de Thuya en forme de cœur",
                description="Boîte décorative en forme de cœur en racine de Thuya",
                prix=280.0,
                image="jjj.webp",
                categorie="jeux_traditionnels",
                stock=12,
                est_nouveaute=False
            ),
            Produit(
                nom="Boîte stylo en loupe de thuya",
                description="Boîte élégante pour ranger les stylos",
                prix=120.0,
                image="mmm.jpg",
                categorie="art_de_la_table",
                stock=15,
                est_nouveaute=False
            ),
            Produit(
                nom="Boîte D'accessoires de thuya",
                description="Boîte pratique pour ranger vos accessoires",
                prix=180.0,
                image="mm.png",
                categorie="accessoires",
                stock=10,
                est_nouveaute=False
            ),
            Produit(
                nom="Boîte organisateur et décor",
                description="Boîte organisateur avec design décoratif",
                prix=240.0,
                image="m.jpg",
                categorie="accessoires",
                stock=8,
                est_nouveaute=False
            )
        ]
        
        for produit in produits_jeux:
            db.session.add(produit)
        
        db.session.commit()
        print("Produits jeux et accessoires ajoutés à la base de données!")


def init_db():
    with app.app_context():
        db.create_all()
        creer_admin_initial()
        
  
        if Produit.query.count() == 0:
           
            produits_test = [
                Produit(
                    nom="Coffret en bois de Thuya avec marqueterie florale en arabesques",
                    description="Magnifique coffret artisanal en bois de Thuya",
                    prix=350.0,
                    image="88.webp",
                    categorie="boites_artisanales",
                    stock=10,
                    est_nouveaute=True
                ),
                Produit(
                    nom="Boîte en bois de Thuya carrée",
                    description="Boîte carrée traditionnelle en bois de Thuya",
                    prix=120.0,
                    image="222.webp",
                    categorie="boites_artisanales",
                    stock=15,
                    est_nouveaute=True
                ),
                Produit(
                    nom="Boîte à Ouverture Secrète Pivotante en Bois",
                    description="Boîte mystérieuse avec mécanisme secret",
                    prix=200.0,
                    image="333.jpg",
                    categorie="boites_artisanales",
                    stock=8,
                    est_nouveaute=True
                ),
                Produit(
                    nom="Coffret en bois de Thuya ",
                    description="Magnifique coffret artisanal ",
                    prix=350.0,
                    image="10.webp",
                    categorie="art_de_la_table",
                    stock=10,
                    est_nouveaute=True
                ),
                Produit(
                    nom="Petite boîte en bois de thuya Art déco populaire",
                    description="Design art déco traditionnel",
                    prix=80.0,
                    image="55.webp",
                    categorie="boites_artisanales",
                    stock=20,
                    est_nouveaute=True
                )
            ]
            
            for produit in produits_test:
                db.session.add(produit)
            
            
            ajouter_produits_jeux()
            
          
            ajouter_produits_art_table()
            
            db.session.commit()
            print("Base de données initialisée avec des produits de test!")

       

def ajouter_produits_art_table():
    
    if Produit.query.filter_by(categorie='art_de_la_table').count() <= 1:
        produits_art_table = [
            Produit(
                nom="Plateau en bois de Thuya",
                description="Plateau traditionnel en bois de Thuya finement travaillé",
                prix=330.0,
                image="1111.webp",
                categorie="art_de_la_table",
                stock=8,
                est_nouveaute=True
            ),
            Produit(
                nom="Plateau ovale en Bois",
                description="Plateau ovale élégant pour vos tables",
                prix=220.0,
                image="aaaa.jpg",
                categorie="art_de_la_table",
                stock=12,
                est_nouveaute=False
            ),
            Produit(
                nom="3 plateaux en placage de loupe de thuya",
                description="Set de 3 plateaux en placage de loupe de thuya",
                prix=500.0,
                image="C.jpg",
                categorie="art_de_la_table",
                stock=5,
                est_nouveaute=True
            ),
            Produit(
                nom="Gasaa' Artisanale en Thuya",
                description="Gasaa traditionnelle artisanale en bois de Thuya",
                prix=300.0,
                image="10.webp",
                categorie="art_de_la_table",
                stock=10,
                est_nouveaute=True
            ),
            Produit(
                nom="Plateau rond en Thuya décoré",
                description="Plateau rond avec motifs traditionnels marocains",
                prix=280.0,
                image="plateau_rond.webp",  
                categorie="art_de_la_table",
                stock=15,
                est_nouveaute=False
            ),
            Produit(
                nom="Service à thé en bois de Thuya",
                description="Service à thé complet avec plateau et accessoires",
                prix=450.0,
                image="service_the.webp",  
                categorie="art_de_la_table",
                stock=6,
                est_nouveaute=True
            )
        ]
        
        for produit in produits_art_table:
            db.session.add(produit)
        
        db.session.commit()
        print("Produits art de la table ajoutés à la base de données!")
            
        db.session.commit()
        print("Base de données initialisée avec des produits de test!")


def ajouter_produits_manquants():
    with app.app_context():
        print("Ajout des produits manquants...")
        ajouter_produits_art_table()
        print("Produits ajoutés avec succès!")

def ajouter_produits_art_table_complets():
 
    with app.app_context():
        
        produits_fixes = [
            {
                'id': 9,
                'nom': "Gasaa' Artisanale en Thuya",
                'description': "Gasaa traditionnelle artisanale en bois de Thuya, pièce unique façonnée à la main par nos artisans d'Essaouira. Le bois de Thuya, précieux et aromatique, confère à cette pièce une beauté naturelle exceptionnelle.",
                'prix': 300.0,
                'image': "10.webp",
                'categorie': "art_de_la_table",
                'stock': 10,
                'est_nouveaute': True
            },
            {
                'id': 10,
                'nom': "Plateau en bois de Thuya",
                'description': "Plateau traditionnel en bois de Thuya finement travaillé avec des motifs géométriques traditionnels. Chaque pièce est unique grâce aux veines naturelles du bois de Thuya.",
                'prix': 330.0,
                'image': "1111.webp",
                'categorie': "art_de_la_table",
                'stock': 8,
                'est_nouveaute': True
            },
            {
                'id': 15,
                'nom': "Plateau ovale en Bois",
                'description': "Plateau ovale élégant parfait pour servir le thé ou décorer votre table. Fabriqué en bois noble avec des finitions soignées qui mettent en valeur le grain naturel.",
                'prix': 220.0,
                'image': "aaaa.jpg",
                'categorie': "art_de_la_table",
                'stock': 12,
                'est_nouveaute': False
            },
            {
                'id': 24,
                'nom': "3 plateaux en placage de loupe de thuya",
                'description': "Set exceptionnel de 3 plateaux en placage de loupe de thuya de différentes tailles. La loupe de thuya offre des motifs marbrés uniques et précieux, faisant de ce set une pièce de collection.",
                'prix': 500.0,
                'image': "C.jpg",
                'categorie': "art_de_la_table",
                'stock': 5,
                'est_nouveaute': True
            }
        ]
        
        for produit_data in produits_fixes:
            produit_existant = Produit.query.get(produit_data['id'])
            
            if not produit_existant:
                nouveau_produit = Produit(
                    nom=produit_data['nom'],
                    description=produit_data['description'],
                    prix=produit_data['prix'],
                    image=produit_data['image'],
                    categorie=produit_data['categorie'],
                    stock=produit_data['stock'],
                    est_nouveaute=produit_data['est_nouveaute']
                )
                db.session.add(nouveau_produit)
                db.session.flush()  
                
                if nouveau_produit.id != produit_data['id']:
                    db.session.delete(nouveau_produit)
                    db.session.flush()
                    
                    db.session.execute(         # nonnnn
                        f"""INSERT INTO produit 
                        (id, nom, description, prix, image, categorie, stock, est_nouveaute, date_creation) 
                        VALUES ({produit_data['id']}, '{produit_data['nom']}', '{produit_data['description']}', 
                        {produit_data['prix']}, '{produit_data['image']}', '{produit_data['categorie']}', 
                        {produit_data['stock']}, {1 if produit_data['est_nouveaute'] else 0}, datetime('now'))"""
                    )
                
                print(f"Produit ajouté: {produit_data['nom']} (ID: {produit_data['id']})")
            else:
                
                produit_existant.nom = produit_data['nom']
                produit_existant.description = produit_data['description']
                produit_existant.prix = produit_data['prix']
                produit_existant.image = produit_data['image']
                produit_existant.categorie = produit_data['categorie']
                produit_existant.stock = produit_data['stock']
                produit_existant.est_nouveaute = produit_data['est_nouveaute']
                print(f"Produit mis à jour: {produit_data['nom']} (ID: {produit_data['id']})")
        
        try:
            db.session.commit()
            print("Tous les produits d'art de la table ont été ajoutés/mis à jour avec succès!")
        except Exception as e:
            db.session.rollback()
            print(f"Erreur lors de l'ajout des produits: {e}")

    ajouter_produits_art_table_complets()



@app.route('/admin')
@login_required
@admin_required
def admin_dashboard():
   
    total_commandes = Commande.query.count()
    commandes_en_attente = Commande.query.filter_by(statut='En attente').count()
    commandes_confirmees = Commande.query.filter_by(statut='Confirmée').count()
    commandes_livrees = Commande.query.filter_by(statut='Livrée').count()   #non
    
    chiffre_affaires = db.session.query(db.func.sum(Commande.total)).scalar() or 0
    commandes_recentes = Commande.query.order_by(Commande.date_commande.desc()).limit(5).all()  
    
    produits_populaires = db.session.query(   
        Produit.nom,
        db.func.sum(CommandeItem.quantite).label('total_vendu')
    ).join(CommandeItem).group_by(Produit.id).order_by(
        db.func.sum(CommandeItem.quantite).desc()
    ).limit(5).all()
    
    return render_template('admin/dashboard.html',
                         total_commandes=total_commandes,
                         commandes_en_attente=commandes_en_attente,
                         commandes_confirmees=commandes_confirmees,
                         commandes_livrees=commandes_livrees,
                         chiffre_affaires=chiffre_affaires,
                         commandes_recentes=commandes_recentes,
                         produits_populaires=produits_populaires)

@app.route('/admin/commandes')
@login_required
@admin_required
def admin_commandes():
   
    page = request.args.get('page', 1, type=int)
    statut_filtre = request.args.get('statut', '')  
    
    query = Commande.query
    
    if statut_filtre:
        query = query.filter_by(statut=statut_filtre)
    
    commandes = query.order_by(Commande.date_commande.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    return render_template('admin/commandes.html', commandes=commandes, statut_filtre=statut_filtre)

@app.route('/admin/commande/<int:commande_id>')
@login_required
@admin_required
def admin_commande_detail(commande_id):
   
    commande = Commande.query.get_or_404(commande_id)
    return render_template('admin/commande_detail.html', commande=commande)

@app.route('/admin/commande/<int:commande_id>/modifier-statut', methods=['POST'])
@login_required
@admin_required
def modifier_statut_commande(commande_id):
    commande = Commande.query.get_or_404(commande_id)
    nouveau_statut = request.form.get('statut')
    
    statuts_valides = ['En attente', 'Confirmée', 'En préparation', 'Expédiée', 'Livrée', 'Annulée']
    
    if nouveau_statut in statuts_valides:
        ancien_statut = commande.statut
        commande.statut = nouveau_statut
        
        try:
            db.session.commit()
            log_user_action('ORDER_STATUS_CHANGED', 
                          {'admin_user': current_user.email}, 
                          {'order_id': commande_id, 'old_status': ancien_statut, 'new_status': nouveau_statut})
            
            flash(f'Statut de la commande #{commande_id} modifié de "{ancien_statut}" à "{nouveau_statut}".', 'success')
            
        except Exception as e:
            db.session.rollback()
            flash('Erreur lors de la modification du statut.', 'error')
    else:
        flash('Statut invalide.', 'error')
    
    return redirect(url_for('admin_commande_detail', commande_id=commande_id))

@app.route('/admin/utilisateurs')
@login_required
@admin_required
def admin_utilisateurs():
    page = request.args.get('page', 1, type=int)# nonnn
    utilisateurs = User.query.order_by(User.date_creation.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    return render_template('admin/utilisateurs.html', utilisateurs=utilisateurs)

@app.route('/admin/produits')
@login_required
@admin_required
def admin_produits():
    page = request.args.get('page', 1, type=int)# non
    produits = Produit.query.order_by(Produit.date_creation.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    return render_template('admin/produits.html', produits=produits)



@app.route('/admin/produit/<int:produit_id>/modifier', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_modifier_produit(produit_id):
    produit = Produit.query.get_or_404(produit_id)
    
    if request.method == 'POST':
        try:

            produit.nom = request.form.get('nom', '').strip()
            produit.description = request.form.get('description', '').strip()
            produit.prix = float(request.form.get('prix', 0))
            produit.categorie = request.form.get('categorie', '').strip()
            produit.stock = int(request.form.get('stock', 0))
            produit.est_nouveaute = 'est_nouveaute' in request.form
            
           
            if not produit.nom or not produit.description:
                flash('Le nom et la description sont obligatoires.', 'error')
                return redirect(url_for('admin_produits'))
            
            if produit.prix < 0 or produit.stock < 0:
                flash('Le prix et le stock doivent être positifs.', 'error')
                return redirect(url_for('admin_produits'))
            
            ancienne_image = produit.image
            
            if 'supprimer_image' in request.form:
                if ancienne_image:
                    delete_image(ancienne_image)
                produit.image = None
           
            if 'image' in request.files:
                file = request.files['image']
                if file and file.filename != '':
                    # taille du imageee
                    file.seek(0, os.SEEK_END)
                    file_size = file.tell()
                    file.seek(0)
                    
                    if file_size > MAX_FILE_SIZE:
                        flash('La taille de l\'image ne doit pas dépasser 5MB.', 'error')
                        return redirect(url_for('admin_produits'))
                    
        
                    nouveau_nom_image = save_uploaded_image(file)
                    if nouveau_nom_image:
                      
                        if ancienne_image and not ('supprimer_image' in request.form):
                            delete_image(ancienne_image)
                        
                        produit.image = nouveau_nom_image
                    else:
                        flash('Format d\'image non supporté. Utilisez JPG, PNG ou GIF.', 'error')
                        return redirect(url_for('admin_produits'))
            
            db.session.commit()
            
            # Logs
            log_user_action('PRODUCT_MODIFIED', 
                          {'admin_user': current_user.email}, 
                          {'product_id': produit_id, 'product_name': produit.nom})
            
            flash(f'Produit "{produit.nom}" modifié avec succès!', 'success')
            return redirect(url_for('admin_produits'))
            
        except ValueError:
            flash('Erreur dans les valeurs numériques (prix, stock).', 'error')
        except Exception as e:
            db.session.rollback()
            flash('Erreur lors de la modification du produit.', 'error')
            print(f"Erreur modification produit: {e}")
    
    return redirect(url_for('admin_produits'))

@app.route('/admin/produit/ajouter', methods=['POST'])  
@login_required
@admin_required
def admin_ajouter_produit():
    try:
        nouveau_produit = Produit(
            nom=request.form.get('nom', '').strip(),
            description=request.form.get('description', '').strip(),
            prix=float(request.form.get('prix', 0)),
            categorie=request.form.get('categorie', '').strip(),
            stock=int(request.form.get('stock', 0)),
            est_nouveaute='est_nouveaute' in request.form
        )
        
       
        if not nouveau_produit.nom or not nouveau_produit.description:
            flash('Le nom et la description sont obligatoires.', 'error')
            return redirect(url_for('admin_produits'))
        
        if nouveau_produit.prix < 0 or nouveau_produit.stock < 0:
            flash('Le prix et le stock doivent être positifs.', 'error')
            return redirect(url_for('admin_produits'))
        
        
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename != '':
                # Vérifier la taille du fichier
                file.seek(0, os.SEEK_END)
                file_size = file.tell()
                file.seek(0)
                
                if file_size > MAX_FILE_SIZE:
                    flash('La taille de l\'image ne doit pas dépasser 5MB.', 'error')
                    return redirect(url_for('admin_produits'))
                
                
                nom_image = save_uploaded_image(file)
                if nom_image:
                    nouveau_produit.image = nom_image
                else:
                    flash('Format d\'image non supporté. Utilisez JPG, PNG ou GIF.', 'error')
                    return redirect(url_for('admin_produits'))
        
        db.session.add(nouveau_produit)
        db.session.commit()
        
        
        log_user_action('PRODUCT_CREATED', 
                      {'admin_user': current_user.email}, 
                      {'product_name': nouveau_produit.nom})
        
        flash(f'Produit "{nouveau_produit.nom}" créé avec succès!', 'success')
        
    except ValueError:
        flash('Erreur dans les valeurs numériques (prix, stock).', 'error')
    except Exception as e:
        db.session.rollback()
        flash('Erreur lors de la création du produit.', 'error')
        print(f"Erreur création produit: {e}")
    
    return redirect(url_for('admin_produits'))

@app.route('/admin/produit/<int:produit_id>/supprimer', methods=['POST'])# non cmplexe
@login_required
@admin_required
def admin_supprimer_produit(produit_id):
    produit = Produit.query.get_or_404(produit_id)
    
    try:
       
        commandes_associees = CommandeItem.query.filter_by(produit_id=produit_id).count()
        
        if commandes_associees > 0:
            flash(f'Impossible de supprimer "{produit.nom}" car il y a {commandes_associees} commande(s) associée(s).', 'error')
        else:
            nom_produit = produit.nom
            image_a_supprimer = produit.image
            
           
            db.session.delete(produit)
            db.session.commit()
            
            
            if image_a_supprimer:
                delete_image(image_a_supprimer)
            
            
            log_user_action('PRODUCT_DELETED', 
                          {'admin_user': current_user.email}, 
                          {'product_name': nom_produit})
            
            flash(f'Produit "{nom_produit}" supprimé avec succès.', 'success')
            
    except Exception as e:
        db.session.rollback()
        flash('Erreur lors de la suppression du produit.', 'error')
        print(f"Erreur suppression produit: {e}")
    
    return redirect(url_for('admin_produits'))


def creer_admin_initial():
    admin_existant = User.query.filter_by(est_admin=True).first()

    if not admin_existant:
        admin_email = os.environ.get('ADMIN_EMAIL', 'admin@example.com')
        admin_password = os.environ.get('ADMIN_PASSWORD')
        mot_de_passe_genere = admin_password is None
        if mot_de_passe_genere:
            admin_password = secrets.token_urlsafe(12)

        admin_user = User(
            nom='Administrateur',
            email=admin_email,
            mot_de_passe=bcrypt.generate_password_hash(admin_password).decode('utf-8'),
            est_admin=True
        )

        db.session.add(admin_user)
        db.session.commit()

        print("Compte administrateur créé:")
        print(f"Email: {admin_email}")
        if mot_de_passe_genere:
            print(f"Mot de passe généré (à noter maintenant): {admin_password}")
        else:
            print("Mot de passe défini avec la variable ADMIN_PASSWORD.")

if __name__ == "__main__":
    init_db()
    app.run(debug=os.environ.get('FLASK_DEBUG') == '1')
