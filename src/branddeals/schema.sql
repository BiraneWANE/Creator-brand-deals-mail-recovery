-- Modèle de données du projet (SQLite, portable vers PostgreSQL sans changement de structure).
--
-- Principe : on conserve la chaîne complète de la preuve.
--   interlocuteur 1──n conversation 1──n message 1──n document
--   interlocuteur 1──1 partenariat (la décision prise après lecture)
-- Toute ligne du tableau final peut donc être remontée jusqu'au mail d'origine.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS interlocuteur (
    cle            TEXT PRIMARY KEY,          -- domaine (marque.fr) ou adresse (messagerie grand public)
    est_messagerie_publique INTEGER NOT NULL DEFAULT 0,
    decision       TEXT NOT NULL CHECK (decision IN ('retenu', 'ecarte', 'a_lire')),
    motif          TEXT                       -- ex. sollicitation_sans_reponse, refus_poli, newsletter
);

CREATE TABLE IF NOT EXISTS conversation (
    id             TEXT PRIMARY KEY,          -- identifiant Gmail de la conversation
    cle_interlocuteur TEXT REFERENCES interlocuteur(cle),
    sujet          TEXT,
    premier_message DATE NOT NULL,
    dernier_message DATE NOT NULL,
    nb_messages    INTEGER NOT NULL CHECK (nb_messages > 0),
    recherches     TEXT NOT NULL,             -- recherches qui l'ont trouvée (traçabilité)
    libelle_pose   INTEGER NOT NULL DEFAULT 0,
    CHECK (dernier_message >= premier_message)
);

CREATE TABLE IF NOT EXISTS partenariat (
    cle_interlocuteur TEXT PRIMARY KEY REFERENCES interlocuteur(cle),
    marque         TEXT NOT NULL,
    contact_nom    TEXT,
    contact_email  TEXT,
    premier_echange DATE NOT NULL,
    dernier_echange DATE NOT NULL,
    type           TEXT NOT NULL CHECK (type IN ('payée','produit offert','UGC','campagne','événement','mixte')),
    statut         TEXT NOT NULL CHECK (statut IN ('payée','en attente','non facturée','abandonnée','inconnu')),
    montant        REAL CHECK (montant IS NULL OR montant >= 0),
    factures       TEXT,
    a_relancer     INTEGER NOT NULL DEFAULT 0,
    remarque       TEXT,
    lien           TEXT
);

CREATE TABLE IF NOT EXISTS document (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    id_conversation TEXT NOT NULL REFERENCES conversation(id),
    id_message     TEXT NOT NULL,
    date_envoi     DATE NOT NULL,
    cle_interlocuteur TEXT NOT NULL REFERENCES interlocuteur(cle),
    nom_fichier    TEXT NOT NULL,
    type           TEXT NOT NULL CHECK (type IN ('facture_emise','facture_recue','contrat','devis','bon_de_commande','brief','autre')),
    numero         TEXT,
    montant        REAL,
    emis_par_creatrice INTEGER NOT NULL DEFAULT 0,
    chemin         TEXT,                      -- NULL : à récupérer à la main
    remarque       TEXT
);

CREATE INDEX IF NOT EXISTS ix_conv_interlocuteur ON conversation(cle_interlocuteur);
CREATE INDEX IF NOT EXISTS ix_doc_type ON document(type);
CREATE INDEX IF NOT EXISTS ix_doc_numero ON document(numero) WHERE numero IS NOT NULL;

-- Vues métier : ce que la créatrice consulte vraiment.
CREATE VIEW IF NOT EXISTS v_a_relancer AS
    SELECT marque, contact_nom, contact_email, dernier_echange, type, remarque, lien
    FROM partenariat WHERE a_relancer = 1 ORDER BY dernier_echange DESC;

CREATE VIEW IF NOT EXISTS v_factures_en_attente AS
    SELECT p.marque, d.numero, d.date_envoi, d.montant, d.chemin
    FROM document d JOIN partenariat p ON p.cle_interlocuteur = d.cle_interlocuteur
    WHERE d.type = 'facture_emise' AND p.statut = 'en attente' ORDER BY d.date_envoi;

CREATE VIEW IF NOT EXISTS v_numeros_factures_reutilises AS
    SELECT numero, COUNT(DISTINCT cle_interlocuteur) AS nb_clients
    FROM document WHERE type = 'facture_emise' AND numero IS NOT NULL
    GROUP BY numero HAVING COUNT(DISTINCT cle_interlocuteur) > 1;

CREATE VIEW IF NOT EXISTS v_activite_par_annee AS
    SELECT strftime('%Y', premier_echange) AS annee, type, COUNT(*) AS nb_partenariats
    FROM partenariat GROUP BY annee, type ORDER BY annee;
