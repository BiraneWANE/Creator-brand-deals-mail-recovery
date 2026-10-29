# Limites connues et suite

## Limites

| Limite | Effet | Ce qui est fait aujourd'hui |
|---|---|---|
| Le lecteur IA peut se tromper | Une collab mal classée (ex. produit offert lu comme payé) | Chaque ligne garde le lien vers le mail ; les montants non confirmés restent vides ; relecture humaine des lignes « à relancer » avant tout envoi |
| Les recherches par mots-clés ne voient pas tout | Une collab conclue sans aucun des mots recherchés est manquée | Deux recherches complémentaires ; la liste des mots se modifie dans `rules.yaml` |
| Les factures scannées n'ont pas de texte | Numéro et montant non lus | Le document est quand même extrait et typé ; OCR possible (non activé par défaut) |
| Factures hors boîte mail | Le total retrouvé sous-estime le chiffre réel | Présenté comme « factures retrouvées », jamais comme un chiffre d'affaires |
| Fils de plus de 100 messages | L'API renvoie les 100 plus récents | Signalé dans la remarque du partenariat |
| Messages au-delà de la taille limite | Documents non téléchargés | Listés avec lien, récupération manuelle |

## Mesurer la qualité du lecteur

La démo et les tests utilisent un lecteur à règles, déterministe. Pour évaluer un lecteur IA sur des données
réelles sans les publier, la méthode prévue est :

1. tirer au hasard 50 interlocuteurs retenus et 50 écartés ;
2. les faire étiqueter à la main par la personne concernée (vrai partenariat ? type ? statut ?) ;
3. mesurer précision et rappel sur « est un partenariat », et exactitude sur le type et le statut ;
4. conserver ce jeu d'évaluation hors dépôt, et ne publier que les scores.

## Suite prévue

- **Phase 2** : fusion avec la nouvelle boîte professionnelle (migration en cours), dédoublonnage entre les deux.
- **Phase 3** : analyse exploratoire de l'activité (saisonnalité, part payée/offerte, fidélité des marques,
  délais de paiement), publiée en proportions uniquement.
- **Phase 4** : passage d'un fichier ponctuel à un suivi continu : tâche planifiée qui lit les nouveaux échanges
  chaque nuit et met à jour la base et les relances.
