/** @odoo-module **/

import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";

/**
 * GPL Fleet Module - JavaScript pour Odoo 17
 * Fonctionnalités client-side pour le module GPL
 */

// === UTILITAIRES GPL ===
const GPLUtils = {

    /**
     * Formate une date pour l'affichage
     */
    formatDate: function(dateString) {
        if (!dateString) return '';
        const date = new Date(dateString);
        return date.toLocaleDateString('fr-FR');
    },

    /**
     * Calcule les jours restants jusqu'à une date
     */
    daysUntilDate: function(dateString) {
        if (!dateString) return null;
        const targetDate = new Date(dateString);
        const today = new Date();
        const diffTime = targetDate - today;
        return Math.ceil(diffTime / (1000 * 60 * 60 * 24));
    },

    /**
     * Retourne la classe CSS selon l'état du réservoir
     */
    getReservoirStatusClass: function(state) {
        const statusClasses = {
            'valid': 'reservoir-status-valid',
            'expiring_soon': 'reservoir-status-expiring',
            'expired': 'reservoir-status-expired',
            'test_required': 'reservoir-status-expired',
            'too_old': 'reservoir-status-expired'
        };
        return statusClasses[state] || '';
    },

    /**
     * Affiche une notification
     */
    showNotification: function(message, type = 'info') {
        if (typeof odoo !== 'undefined' && odoo.notification) {
            odoo.notification.add(message, { type: type });
        } else {
            console.log(`[GPL ${type.toUpperCase()}] ${message}`);
        }
    }
};

// === COMPOSANT DASHBOARD RÉSERVOIRS ===
class GPLReservoirDashboard extends Component {
    static template = "gpl_fleet.ReservoirDashboard";

    setup() {
        this.GPLUtils = GPLUtils;
    }

    /**
     * Actualise les statistiques du dashboard
     */
    async refreshStats() {
        try {
            GPLUtils.showNotification("Actualisation des statistiques...", "info");
            // Ici on pourrait faire un appel RPC pour actualiser les données
            // const result = await this.rpc('/gpl_fleet/refresh_stats');
            GPLUtils.showNotification("Statistiques actualisées", "success");
        } catch (error) {
            GPLUtils.showNotification("Erreur lors de l'actualisation", "danger");
            console.error("GPL Dashboard refresh error:", error);
        }
    }

    /**
     * Ouvre la vue détaillée d'un réservoir
     */
    openReservoirDetails(reservoirId) {
        if (!reservoirId) return;

        this.env.services.action.doAction({
            type: 'ir.actions.act_window',
            res_model: 'stock.lot',
            res_id: reservoirId,
            view_mode: 'form',
            target: 'current'
        });
    }
}

// === FONCTIONS UTILITAIRES GLOBALES ===
window.GPLFleet = window.GPLFleet || {};
window.GPLFleet.Utils = GPLUtils;

/**
 * Initialise les fonctionnalités GPL au chargement de la page
 */
function initGPLFeatures() {
    console.log("GPL Fleet Module - Fonctionnalités JavaScript initialisées");

    // Ajouter des event listeners pour les boutons GPL
    document.addEventListener('click', function(event) {
        const target = event.target;

        // Bouton d'actualisation des stats
        if (target.classList.contains('gpl-refresh-stats')) {
            event.preventDefault();
            GPLUtils.showNotification("Actualisation en cours...", "info");
        }

        // Boutons d'alerte réservoir
        if (target.classList.contains('gpl-reservoir-alert')) {
            const reservoirId = target.dataset.reservoirId;
            if (reservoirId) {
                GPLUtils.showNotification(`Réservoir ${reservoirId} nécessite une attention`, "warning");
            }
        }
    });

    // Initialiser les tooltips GPL
    initGPLTooltips();
}

/**
 * Initialise les tooltips spécifiques GPL
 */
function initGPLTooltips() {
    const tooltipElements = document.querySelectorAll('[data-gpl-tooltip]');

    tooltipElements.forEach(element => {
        const tooltipText = element.dataset.gplTooltip;
        element.title = tooltipText;

        // Ajouter un style visuel pour indiquer la présence d'un tooltip
        element.style.cursor = 'help';
        element.style.borderBottom = '1px dotted #999';
    });
}

/**
 * Fonction de calcul dynamique pour les dates d'expiration
 */
function updateExpiryCountdowns() {
    const countdownElements = document.querySelectorAll('.gpl-expiry-countdown');

    countdownElements.forEach(element => {
        const expiryDate = element.dataset.expiryDate;
        if (!expiryDate) return;

        const daysLeft = GPLUtils.daysUntilDate(expiryDate);

        if (daysLeft !== null) {
            element.textContent = daysLeft > 0 ?
                `${daysLeft} jours restants` :
                `Expiré depuis ${Math.abs(daysLeft)} jours`;

            // Mettre à jour la classe CSS selon l'urgence
            element.className = 'gpl-expiry-countdown ' +
                (daysLeft <= 0 ? 'text-danger' :
                 daysLeft <= 30 ? 'text-warning' : 'text-success');
        }
    });
}

// === ENREGISTREMENT DES COMPOSANTS ===
// Enregistrer le composant dashboard si OWL est disponible
if (typeof registry !== 'undefined') {
    registry.category("components").add("GPLReservoirDashboard", GPLReservoirDashboard);
}

// === INITIALISATION AU CHARGEMENT ===
// S'assurer que le DOM est chargé avant d'initialiser
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initGPLFeatures);
} else {
    initGPLFeatures();
}

// Mettre à jour les compteurs toutes les minutes
setInterval(updateExpiryCountdowns, 60000);

// Export pour utilisation dans d'autres modules
export { GPLUtils, GPLReservoirDashboard };
