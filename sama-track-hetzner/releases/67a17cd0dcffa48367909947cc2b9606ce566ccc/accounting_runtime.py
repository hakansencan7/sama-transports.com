# Preserve the existing, working print/login patch chain first.
import print_audit_patch as print_patch

# Then register the accounting database migration/redirect startup hook.
import accounting_db_patch as accounting_patch

# Run the one-time backed-up shipment reset. This is intentionally imported
# after accounting migration registration so accounting history is preserved.
import shipment_reset_once as shipment_reset

# Restore the vehicle master from the pre-reset backup without restoring trips.
# This keeps historical plate autocomplete available after a clean shipment reset.
import restore_plate_master_from_backup as plate_master_restore

# Keep plate autocomplete independent from trip history. After a shipment DB
# reset, suggestions come from restored/current vehicle master lists first.
import plate_autocomplete_patch as plate_autocomplete

# Explicitly attach autocomplete when the New Shipment plate field gets focus.
# MutationObserver auto-attachment was not reliable inside the modal.
import plate_autocomplete_ui_patch as plate_autocomplete_ui

# New shipments use KG by default; ADET is the secondary freight unit.
import kg_freight_patch as kg_freight

# ADMIN fleet plate deletion, implemented inside the existing JS block only.
import fleet_delete_safe_patch as fleet_delete_safe

# After a successful Entry save, offer printing immediately instead of forcing
# the user to switch the list filter to COMPLETED first.
import entry_print_after_save_patch as entry_print_after_save

# QR driver mobile status page + GPS tracker review queue.
import driver_qr_status_patch as driver_qr_status

# Harden public QR tokens without changing existing valid printed links.
import driver_qr_security_patch as driver_qr_security

# Visual-first driver page for drivers who cannot reliably read text.
import driver_qr_visual_patch as driver_qr_visual

# The QR printed on shipment forms must open the visual driver status page.
import print_qr_driver_link_patch as print_qr_driver_link

# Force the actual print HTML (both EXIT and ENTRY forms) to load the
# driver-status QR endpoint instead of the legacy SCNA-only QR image.
import print_qr_src_fix_patch as print_qr_src_fix

# Make pending driver reports visible and reviewable from the main app.
import driver_status_monitor_fix_patch as driver_status_monitor_fix

# Move driver notifications into the Operations area/navigation.
import driver_status_operation_integration_patch as driver_status_operation_integration

# Once GPS/operator approves RETURNING, synchronize the main operations state
# so the vehicle is rendered as DONUYOR on the dashboard.
import driver_status_main_sync_patch as driver_status_main_sync

# Hide driver account difference from the main dashboard only.
import dashboard_remove_driver_diff_patch as dashboard_remove_driver_diff

# Entry: fixed bilingual WEIGHBRIDGE / PARKING / WAITING expenses with
# quantity x unit-price calculation and a sticky live summary panel.
import entry_fixed_expenses_patch as entry_fixed_expenses

# Entry: two free-form OTHER rows (amount + description), included in settlement,
# and itemized print rows for fixed expenses and OTHER details.
import entry_other_and_print_items_patch as entry_other_and_print_items

# KolayBi web module: separate persistent master DB for product/contact/project IDs,
# management UI inside SAMA TRACK, and SCNA mapping preview.
import kolaybi_web_module_patch as kolaybi_web_module

# KolayBi API synchronization: contacts, products, projects and CommercialDoc tags.
# Credentials remain server-side in Railway environment variables or persistent web settings.
import kolaybi_sync_patch as kolaybi_sync

# Safe real-send flow: purchase invoice payload, default tags and duplicate guard.
import kolaybi_send_patch as kolaybi_send

# Web-managed KolayBi connection fallback + token/source diagnostics.
# Secrets are stored only in the persistent /data DB, never committed to GitHub.
import kolaybi_connection_settings_patch as kolaybi_connection_settings

# Search/filter boxes for products, contacts, projects and tags.
import kolaybi_search_filters_patch as kolaybi_search_filters

# Auto-link SAMA fixed expense codes to exactly one matching synced KolayBi product.
import kolaybi_auto_mapping_patch as kolaybi_auto_mapping

# Complete KolayBi expense set with PORT FEE, DOCK FEE, SONAR and EXIT OTHER.
import kolaybi_complete_expenses_patch as kolaybi_complete_expenses

# Show exact preview missing reasons and safely auto-match one normalized contact.
import kolaybi_preview_diagnostic_patch as kolaybi_preview_diagnostic

# Toplu Ödeme-inspired single-SCNA workspace, with PURCHASE and SALE split.
import kolaybi_single_transaction_ui_patch as kolaybi_single_transaction_ui

# Authoritative KolayBi workflow copied from the proven desktop/Streamlit logic:
# PURCHASE resolves cari by plate/FREIGHT; SALE resolves customer + route product alias.
import kolaybi_workflow_v2_patch as kolaybi_workflow_v2

# Final V2 safeguards: migrate old purchase history, normalize aliases, and expose one-click refresh.
import kolaybi_workflow_v2_finish_patch as kolaybi_workflow_v2_finish

# V3 contact resolver: score duplicate FREIGHT plate records, live-resolve customer names,
# fetch Address ID on demand, and keep SALE KG/ADET semantics independent of product-card unit labels.
import kolaybi_contact_resolution_v3_patch as kolaybi_contact_resolution_v3

# Keep bulk associate refresh fast: list sync is shallow; detail/address calls happen only for the SCNA being prepared.
import kolaybi_contact_resolution_v3_perf_fix_patch as kolaybi_contact_resolution_v3_perf_fix

# Restore the remaining purchase lines from the proven old INVOICE engine:
# allowance/premium and the three exit fuel blocks, still using exact KolayBi Product IDs.
import kolaybi_legacy_invoice_items_patch as kolaybi_legacy_invoice_items

# Final single-pass SALE preview: customer resolution happens once and KG/ADET comes from shipment basis.
import kolaybi_transaction_preview_final_patch as kolaybi_transaction_preview_final

# Explicit KolayBi document metadata: surface serial/document numbers, editable invoice description,
# and the old program's remote serial-cache duplicate protection for PURCHASE vs SALE separately.
import kolaybi_invoice_metadata_serial_patch as kolaybi_invoice_metadata_serial

# Never show a vague EKSİK badge: print the exact blocking Product/Contact/Address/Project reason.
import kolaybi_missing_reason_badge_patch as kolaybi_missing_reason_badge

# PURCHASE cari ambiguity rule: if a plate has both FREIGHT and REPAIR/SERVICE caris,
# the freight invoice must use the FREIGHT cari. REPAIR is never selected for shipment purchase invoices.
import kolaybi_purchase_freight_priority_patch as kolaybi_purchase_freight_priority

# SALE cari follows the proven desktop workflow: correct/search customer name, choose one DB/API candidate,
# or explicitly create a new KolayBi customer + invoice address when no suitable cari exists.
import kolaybi_sale_cari_workflow_patch as kolaybi_sale_cari_workflow

# Old SALE flow also validates/fills the customer's tax office before the invoice is posted.
import kolaybi_sale_tax_office_guard_patch as kolaybi_sale_tax_office_guard

# Authoritative serial duplicate check: refresh real KolayBi /invoices data automatically,
# classify plain `invoice` rows as PURCHASE, keep PURCHASE/SALE separate, and block send if verification fails.
import kolaybi_serial_live_check_patch as kolaybi_serial_live_check

# Older/imported trips can have RETURN EXTRA EXPENSES only in entry_extra_expense_1..3.
# Recover those rows into PURCHASE when the newer fixed-expense metadata table has no corresponding slot.
import kolaybi_return_extra_purchase_patch as kolaybi_return_extra_purchase

# Edit Center can now correct a mistyped SCNA and migrate all shipment-domain child rows safely.
import shipment_scna_rename_patch as shipment_scna_rename

# Stronger than freshness-cache logic: every KolayBi SCNA preview and every real send
# performs a fresh /invoices scan now; stale local memory is never accepted as VAR/YOK evidence.
import kolaybi_serial_force_live_patch as kolaybi_serial_force_live

# Backend-only sent-state reconciliation. It deliberately does not modify HTML/login JS:
# the green sent state exists only when KolayBi /invoices currently contains that PURCHASE/SALE serial.
import kolaybi_remote_sent_backend_safe_patch as kolaybi_remote_sent_backend_safe

# Preserve SAMA's real per-line OTHER explanations in the KolayBi purchase invoice.
# Backend-only: EXIT OTHER uses exit_other_note; ENTRY OTHER keeps entry_other_note_1/2.
import kolaybi_other_description_patch as kolaybi_other_description

# When a SALE route product is missing, stop the send and guide the operator through
# existing-product search/mapping or explicit confirmed creation of a new KolayBi product.
import kolaybi_sale_product_workflow_patch as kolaybi_sale_product_workflow

# Guarantee the two resolver actions are visible directly in the SALE card whenever Product ID is missing.
# This is an inline existing-JS template patch only; no extra script/login block is added.
import kolaybi_sale_product_inline_actions_patch as kolaybi_sale_product_inline_actions

# KolayBi 429 protection: one throttled /invoices scan per UI burst, never dozens of
# immediate fallback calls. Still fail-closed and never use stale DB as VAR/YOK proof.
import kolaybi_serial_rate_limit_patch as kolaybi_serial_rate_limit

# Final serial mode: download KolayBi invoice serials only when the operator presses
# SERIAL DB YENILE. Normal SCNA checks and sends read the persistent local snapshot only.
import kolaybi_serial_manual_cache_patch as kolaybi_serial_manual_cache

# After a successful SAMA -> KolayBi send, add that newly created serial to the local
# snapshot immediately so duplicate protection stays correct without another API scan.
import kolaybi_serial_manual_sent_sync_patch as kolaybi_serial_manual_sent_sync

# Final RETURN EXTRA description resolver: legacy OTHER rows use their real stored notes
# (dedicated note, surviving label, newer OTHER note or entry note) in preview and send.
import kolaybi_return_extra_description_final_patch as kolaybi_return_extra_description_final

# One-button manual serial refresh now downloads PURCHASE and SALE as independent full
# streams, including historical plain type=invoice purchase documents, then merges them.
import kolaybi_serial_dual_kind_snapshot_patch as kolaybi_serial_dual_kind_snapshot

# Separate accountant-control workspace: bulk pasted serials are checked locally against
# PURCHASE + SALE + GENERAL EXPENSE documents, preserving duplicate serials and amounts.
import kolaybi_bulk_accounting_audit_patch as kolaybi_bulk_accounting_audit

# Older compatibility layer for GENERAL EXPENSE reads.
import kolaybi_general_expense_scope_fix_patch as kolaybi_general_expense_scope_fix

# Final correction: use the official /invoices General Expense list with the normal
# KolayBi access-token flow. Remove the temporary extra-token card from the UI.
import kolaybi_general_expense_v1_read_patch as kolaybi_general_expense_v1_read

# One-click bridge: pull SAMA Daily Expense document numbers + amounts from muhasebe.db,
# load them into the KolayBi accounting audit list, then run the existing local comparison.
import kolaybi_daily_expense_audit_bridge_patch as kolaybi_daily_expense_audit_bridge

# Daily Cash page: search document number, note, amount, date, currency and every stored
# field across the entire accounting history in muhasebe.db, not only today's rows.
import cash_daily_history_search_patch as cash_daily_history_search

# Entry correction UX: OTHER is live in settlement calculations; completed Entry records
# open read-only for review and can be explicitly unlocked with DÜZELT by shipment editors.
import entry_other_edit_unlock_patch as entry_other_edit_unlock

# Complete section-level authorization, including KolayBi, Finance, Advances and
# Daily Cash. Load this before security_hardening so the security wrapper captures
# the final permission mapper rather than the older incomplete one.
import section_permissions_patch as section_permissions

# Apply the same authorization/cookie/docs hardening on Railway and Hetzner.
import security_hardening_patch as security_hardening

app = print_patch.app
