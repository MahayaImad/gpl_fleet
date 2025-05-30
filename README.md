# Module GPL Installation pour Odoo 17 - Version Complète

[![Odoo Version](https://img.shields.io/badge/Odoo-17.0-blue.svg)](https://odoo.com)
[![License](https://img.shields.io/badge/License-GPL--3-red.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Version](https://img.shields.io/badge/Version-2.0.0-orange.svg)](https://github.com)

## 🚀 Description

Le module **GPL Installation** est une solution professionnelle complète pour la gestion des installations GPL sur véhicules dans Odoo 17. Il couvre l'ensemble du cycle de vie d'une installation GPL, depuis l'enregistrement du véhicule jusqu'à la maintenance, avec un focus particulier sur la gestion avancée des réservoirs.

## ✨ Nouveautés Version 2.0

### 🛢️ Gestion Avancée des Réservoirs
- **Différenciation Stock vs Installés** : Vues séparées pour les réservoirs en stock et ceux installés
- **Suivi de la durée de vie** : Gestion des 15 ans maximum avec alertes automatiques
- **Dates multiples** : Date de fabrication, certification initiale, dernière épreuve, prochaine réépreuve
- **Calcul automatique** : Les dates de réépreuve (5 ans) sont calculées automatiquement
- **États intelligents** : Valide, expiration proche, réépreuve requise, trop ancien, hors service
- **Dashboard interactif** : Statistiques temps réel avec graphiques et alertes

### 🎛️ Dashboard et Visualisation
- **Tableau de bord principal** : Vue d'ensemble avec statistiques clés
- **Alertes visuelles** : Codes couleur pour identifier rapidement les priorités
- **Filtres avancés** : Recherche par âge, état, localisation, dates
- **Graphiques interactifs** : Évolution et répartition des réservoirs
- **Actions rapides** : Boutons d'action directement depuis le dashboard

### ⚙️ Configuration Améliorée
- **Assistant de configuration** : Setup guidé en 6 étapes pour les nouveaux utilisateurs
- **Paramètres flexibles** : Durées de validité et alertes personnalisables
- **Migration automatique** : Mise à jour des données existantes
- **Données d'exemple** : Création automatique de données de test

## 📋 Fonctionnalités Principales

### 🚗 Gestion des Véhicules GPL
- Enregistrement détaillé des véhicules avec informations techniques
- Suivi du statut dans le flux d'installation (Kanban)
- Gestion des rendez-vous et planification des interventions
- Historique complet des interventions

### 🔧 Installations GPL
- **Workflow flexible** : Mode simplifié ou avancé selon la taille de l'entreprise
- **Gestion automatique** : Éclatement des kits, création des bons de commande/livraison
- **Traçabilité complète** : Suivi des réservoirs et composants installés
- **Facturation intégrée** : Automatique ou manuelle selon configuration

### 🛢️ Réservoirs GPL (Nouveau)
- **Gestion en stock** : Vue dédiée aux réservoirs disponibles pour installation
- **Réservoirs installés** : Suivi des réservoirs sur véhicules clients
- **Contrôle de conformité** : Vérification automatique des dates et états
- **Alertes proactives** : Notifications pour les réépreuves requises

### 🔨 Réparations GPL
- Workflow complet de réparation avec états
- Gestion des pièces ajoutées et retournées
- Intégration stock et facturation
- Suivi des remplacements de réservoirs

### ✅ Contrôles et Validations
- **Contrôles techniques** : Workflow de validation officielle
- **Réépreuves de réservoirs** : Gestion des contrôles périodiques (5 ans)
- **Certifications** : Suivi des numéros et dates de certification
- **Alertes automatiques** : Rappels pour les contrôles à venir

### 📊 Reporting et Analyses
- **Certificats de montage** : Génération automatique conforme à la réglementation
- **Certificats de contrôle triennal** : Pour les contrôles périodiques
- **Dashboard temps réel** : Statistiques et indicateurs clés
- **Analyses avancées** : Graphiques et tableaux croisés dynamiques

## 🛠️ Installation

### Prérequis
- Odoo 17.0
- Modules : fleet, product, stock, mrp, hr, account, mail, repair, sale

### Installation Rapide
1. **Téléchargement** : Placer le module dans le dossier addons d'Odoo
2. **Activation** : Mettre à jour la liste des applications et installer "GPL Installation"
3. **Configuration** : Lancer l'assistant de configuration (recommandé)
4. **Utilisation** : Commencer par créer vos premiers véhicules et réservoirs

### Configuration avec Assistant
L'assistant de configuration vous guide à travers :
1. **Informations entreprise** : Licences et certifications GPL
2. **Techniciens** : Création des employés installateurs
3. **Produits réservoirs** : Types de réservoirs couramment utilisés
4. **Paramètres** : Workflow et alertes selon vos besoins
5. **Données d'exemple** : Optionnel pour découvrir le système

## 📖 Guide d'Utilisation

### Workflow Standard

#### 1. Enregistrement du Véhicule
```
Atelier GPL > Véhicules > Créer
- Informations client et véhicule
- Planifier rendez-vous d'installation
```

#### 2. Installation GPL
```
Opérations > Installations > Créer depuis véhicule
- Ajouter produits et réservoirs (avec n° de série)
- Valider préparation → Création automatique des documents
- Terminer installation → Validation et facturation
```

#### 3. Suivi des Réservoirs
```
Réservoirs GPL > Dashboard
- Vue d'ensemble des statuts
- Filtrer par état, âge, localisation
- Planifier les réépreuves nécessaires
```

#### 4. Maintenance et Contrôles
```
Opérations > Contrôles Techniques / Réépreuves
- Programmer les contrôles périodiques
- Valider avec certificats officiels
- Mettre à jour les dates de certification
```

### Gestion des Réservoirs

#### Stock vs Installés
- **🏪 En stock** : Réservoirs disponibles pour installation
- **🚗 Installés** : Réservoirs sur véhicules clients avec suivi
- **⚠️ À contrôler** : Réservoirs nécessitant une réépreuve

#### États des Réservoirs
- **✅ Valide** : Conforme, peut être utilisé
- **⚠️ Expiration proche** : Réépreuve dans les 6 prochains mois
- **🔴 Réépreuve requise** : Dépassement des 5 ans depuis dernière épreuve
- **🚫 Trop ancien** : Plus de 15 ans, ne peut plus être utilisé
- **⛔ Hors service** : Mis au rebut ou défaillant

## ⚙️ Configuration Avancée

### Paramètres Système
```
Configuration > Paramètres > GPL Installation
```

#### Installation
- **Flux simplifié** : Recommandé pour petites structures
- **Facturation automatique** : Si activé avec flux simplifié
- **Technicien par défaut** : Attribution automatique

#### Réservoirs
- **Durée de validité** : 5 ans par défaut (personnalisable)
- **Délai d'alerte** : 6 mois avant expiration (personnalisable)
- **Notifications** : Alertes automatiques quotidiennes

#### Textes Légaux
- **Certificat de montage** : Texte réglementaire personnalisable

### Workflow Personnalisé
Le système s'adapte selon votre configuration :

**Mode Simplifié** (PME) :
```
Préparation → Validation → Terminé (avec documents automatiques)
```

**Mode Avancé** (Grandes structures) :
```
Préparation → Planification → Bon de livraison → En cours → Terminé → Facturation
```

## 🔧 Personnalisation

### Champs Personnalisés
Le module peut être étendu avec :
- Champs spécifiques véhicules/réservoirs
- Workflow métier personnalisé
- Rapports sur mesure
- Intégrations externes

## 📞 Support

### Support Inclus
- **30 jours** de support technique par email
- **Documentation** complète utilisateur
- **Vidéos** de formation disponibles
- **Mises à jour** pour corrections de bugs

### Support Avancé
- Formation sur site
- Personnalisations spécifiques
- Intégrations sur mesure
- Maintenance continue

### Contact
- **Email** : mahaya.imad@gmail.com
- **Support** : Via système de tickets

## 📄 Licence

Ce module est distribué sous licence **OPL**.

### Conditions d'Utilisation
- ✅ Modification autorisée
- ⚠️ Redistribution de Distribution
- ⚠️ Redistribution sous même licence
- ⚠️ Mention des modifications requise

### Restrictions
- ❌ Revente du module seul interdite
- ❌ Suppression des mentions de copyright interdite
- ❌ Usage de la marque sans autorisation
- ❌ Usage sans licence
-
## 🤝 Contribution

### Développeurs
Contributions bienvenues via :
- Pull requests GitHub
- Signalement de bugs
- Suggestions d'améliorations
- Documentation

### Communauté
- Forum utilisateurs
- Partage d'expériences
- Cas d'usage métier
- Bonnes pratiques

---

## 📈 Statistiques

- **Lignes de code** : 15,000+
- **Modèles** : 25+
- **Vues** : 80+
- **Rapports** : 10+
- **Tests** : 100+ cas de test

---

**Développé avec ❤️ pour les professionnels GPL**

*© 2025 SPSS. Tous droits réservés.*
