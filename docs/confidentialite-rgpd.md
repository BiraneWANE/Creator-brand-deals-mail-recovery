# Confidentialité et RGPD

Une boîte mail professionnelle contient des données personnelles de tiers (contacts chez les marques,
agences) et des données commerciales sensibles (tarifs, factures, contrats). Le projet est construit pour
qu'aucune de ces données ne sorte de chez la personne concernée, et pour que cette garantie ne repose pas
sur la seule vigilance de l'opérateur.

## Ce qui est publié ici, et ce qui ne l'est jamais

| Publié dans ce dépôt | Jamais publié |
|---|---|
| Le code, la méthode, les règles métier | Les mails, pièces jointes, contrats, factures |
| Des comptages agrégés (nombre de conversations, de partenariats par année et par type) | Les noms de marques, de contacts, les adresses |
| Une boîte 100 % fictive en `example.com` pour la démonstration | Tout montant, tarif ou chiffre d'affaires |

## Garde-fous techniques

| Risque | Protection |
|---|---|
| Publier un fichier de données par erreur | `.gitignore` sur tous les formats de données (pdf, xlsx, zip, sqlite, jsonl…) **et** [`check_no_pii.py`](../scripts/check_no_pii.py) qui bloque le commit (hook git) et le push (CI) |
| Publier une adresse, un téléphone, un IBAN, un SIREN, une clé d'API | Même script : seules les adresses en `example.com` / `example.org` sont tolérées |
| Envoyer des données personnelles à un modèle d'IA | [`privacy.mask`](../src/branddeals/privacy.py) remplace téléphones, IBAN, numéros de carte, adresses postales et mails par des jetons **avant** l'appel ; seul le domaine de la marque est conservé |
| Modifier ou détruire la boîte | Droits OAuth limités à la lecture et aux libellés : envoi et suppression sont impossibles côté Google, pas seulement interdits dans le code |
| Fuite des identifiants | `token.json`, `credentials.json`, `.env` exclus du dépôt et refusés par le garde-fou |

## Principes appliqués

- **Minimisation** : seules les conversations correspondant aux deux recherches ciblées sont lues ; seuls les messages porteurs d'un document sont téléchargés ; l'historique cité est retiré avant lecture.
- **Finalité** : la base sert à la gestion de la relation commerciale de la créatrice avec des professionnels (intérêt légitime). Elle ne sert pas à prospecter des particuliers.
- **Exactitude** : un montant non confirmé par écrit reste vide ; chaque ligne garde le lien vers le mail d'origine pour vérification.
- **Conservation** : les données restent sur le poste de la personne concernée ; la base peut être régénérée à tout moment à partir de la boîte, elle n'a donc pas à être archivée ailleurs.
- **Données bancaires** : un RIB trouvé en pièce jointe pendant la mission réelle a été écarté de l'extraction ; la règle est inscrite dans le filtrage des pièces jointes.

## Pseudonymisation des statistiques

Les agrégats publiés ([`docs/figures/agregats.json`](figures/agregats.json)) ne contiennent que des comptages.
Pour toute statistique par interlocuteur, utiliser [`privacy.pseudonym`](../src/branddeals/privacy.py) : un
identifiant SHA-256 tronqué et salé, stable d'une exécution à l'autre et non réversible.
