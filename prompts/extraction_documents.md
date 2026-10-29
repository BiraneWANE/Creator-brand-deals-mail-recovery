# Consigne d'extraction des contrats et factures

Version anonymisée de la consigne donnée aux 4 sous-agents d'extraction pendant la mission réelle
(147 conversations porteuses de documents, réparties en 4 lots traités en parallèle).
Le module [`documents.py`](../src/branddeals/documents.py) en est la version industrialisée.

---

Pour chaque conversation du lot :

1. Liste les messages et repère ceux qui portent une pièce jointe utile : PDF, Word, ou image dont le nom
   évoque un document commercial (facture, contrat, devis, bon de commande, brief, convention).
   Ignore les images de signature et les logos.
2. Pour ces messages seulement, télécharge les pièces jointes et range-les par interlocuteur, préfixées par la
   date d'envoi (AAAA-MM-JJ_nom.pdf).
3. Lis les premières lignes de chaque PDF. Facture émise par la créatrice (reconnaissable à son en-tête) :
   relève numéro, date imprimée, client, montant. Contrat : parties, date, montant s'il figure.
4. Écris une ligne JSON par document (conversation, message, date, interlocuteur, fichier, type, numéro,
   montant, émetteur, remarque).
5. Un message trop lourd pour être téléchargé ne bloque rien : écris sa ligne avec fichier vide et la remarque
   « à récupérer à la main ».
6. Une pièce jointe contenant des coordonnées bancaires (RIB) n'est pas conservée.

Supprime les fichiers bruts intermédiaires après extraction. Ne modifie rien dans la boîte.
