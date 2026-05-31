import { useTranslation } from 'react-i18next';

import { Modal } from './Modal';

interface Props {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void;
  title?: string;
  message: string;
  confirmLabel?: string;
  loading?: boolean;
  destructive?: boolean;
}

export function ConfirmDialog({
  open, onClose, onConfirm,
  title,
  message,
  confirmLabel,
  loading,
  destructive = true,
}: Props) {
  const { t } = useTranslation();
  return (
    <Modal
      open={open}
      onClose={onClose}
      title={title ?? t('common.areYouSure')}
      size="sm"
      footer={
        <>
          <button onClick={onClose} className="btn-secondary" disabled={loading}>
            {t('common.cancel')}
          </button>
          <button
            onClick={onConfirm}
            className={destructive ? 'btn-danger' : 'btn-primary'}
            disabled={loading}
          >
            {loading ? t('common.working') : (confirmLabel ?? t('common.confirm'))}
          </button>
        </>
      }
    >
      <p className="text-sm text-slate-600">{message}</p>
    </Modal>
  );
}
