# Choix et arbitrages

Chaque décision est notée avec ce qui a été écarté et pourquoi : c'est ce qui permet de la remettre en
cause proprement le jour où le contexte change.

## 1. Partir des mails envoyés, pas de toute la boîte

- **Décision** : les deux recherches portent sur `in:sent`.
- **Pourquoi** : une collaboration réelle laisse toujours une réponse de la créatrice. La boîte reçoit
  chaque semaine des dizaines de sollicitations de masse ; les lire coûterait cher pour ne rien trouver.
- **Écarté** : lire toute la boîte de réception (12 386 conversations) ; filtrer uniquement par mots-clés
  sur les mails reçus (trop de bruit).
- **Limite assumée** : une marque qui a écrit sans jamais recevoir de réponse n'apparaît pas. C'est voulu :
  ce n'est pas un partenariat.

## 2. Regrouper par interlocuteur avant de lire

- **Décision** : une lecture par marque (toutes ses conversations ensemble), pas une lecture par mail.
- **Pourquoi** : une collab s'étale sur plusieurs fils (proposition, contrat, facture, relance). Lire fil par
  fil produit des doublons et des statuts contradictoires. Et 667 lectures coûtent bien moins que 1 379.

## 3. Des règles gratuites avant le modèle

- **Décision** : `prefilter` écarte sans IA les sollicitations sans réponse, les refus polis courts et les
  newsletters.
- **Pourquoi** : ce sont les cas les plus nombreux et les plus faciles. Les règles sont explicables, rejouables,
  modifiables dans `rules.yaml` par une personne non technique.

## 4. Sortie du modèle imposée par un schéma

- **Décision** : appel d'outil forcé avec schéma JSON (`PARTNERSHIP_SCHEMA`), énumérations identiques aux
  contraintes `CHECK` de la base.
- **Pourquoi** : un texte libre devrait être réinterprété ; un schéma rend la sortie vérifiable, et une valeur
  hors liste est rejetée deux fois (validation du schéma, puis contrainte SQL).
- **Interchangeable** : le lecteur est une interface (`Reader`). Changer de fournisseur ne touche qu'à `_call`.

## 5. La règle de relance est appliquée par le code

- **Décision** : le lecteur dit seulement si le contact était chaleureux ; « à relancer » est calculé ensuite,
  de façon uniforme (`apply_relance_rule`).
- **Pourquoi** : constaté sur la mission réelle. Laissée à l'appréciation de chaque lecteur, la même règle a été
  appliquée de deux façons différentes selon les lots. Une politique commerciale ne doit pas dépendre du lot.

## 6. Une seule écriture dans la boîte : le libellé

- **Décision** : le pipeline pose le libellé « Partenariats » et rien d'autre.
- **Pourquoi** : la créatrice retrouve tout d'un clic dans Gmail, sans rien perdre ni déplacer. Archivage, tri et
  suppression restent des décisions humaines.

## 7. Les messages trop lourds ne bloquent pas

- **Décision** : au-delà de la taille téléchargeable, le message est listé (onglet « À télécharger à la main »)
  avec le lien vers le mail.
- **Pourquoi** : sur la mission réelle, 13 messages de 7 à 35 Mo (vidéos, visuels de campagne) dépassaient la
  limite de l'outil d'accès. Un traitement qui s'arrête sur une erreur ne livre rien ; un traitement qui la
  documente livre tout le reste et une liste courte à finir à la main.

## 8. Une facture envoyée deux fois compte une fois, un numéro réutilisé est une alerte

- **Décision** : doublon = même numéro, même client, même montant. Même numéro pour deux clients différents :
  alerte « important ».
- **Pourquoi** : en France, la numérotation des factures doit être unique et continue. Ce contrôle, que
  personne ne pense à faire à la main sur six ans de factures, est une valeur ajoutée directe pour la personne accompagnée.

## 9. SQLite d'abord

- **Décision** : SQLite, schéma compatible PostgreSQL.
- **Pourquoi** : un fichier unique, zéro serveur, idéal pour un usage individuel. Le passage à PostgreSQL est
  prévu dans la structure (types standards, contraintes, vues) pour l'étape CRM partagé.
