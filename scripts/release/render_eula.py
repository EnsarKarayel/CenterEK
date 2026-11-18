"""Render a review draft from one publisher profile; never create legal approval."""
import argparse
import json
from pathlib import Path
import re


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--profile', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    profile = json.loads(args.profile.read_text(encoding='utf-8'))
    if not profile.get('seller') or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', profile.get('support_email', '')) or profile.get('subscription_model') != 'annual':
        raise ValueError('Seller, support email and annual subscription model required')
    root = Path(__file__).resolve().parents[2]
    text = (root / 'legal/EULA-DRAFT.tr.txt').read_text(encoding='utf-8')
    fields = {'SELLER': profile['seller'], 'COUNTRY': profile.get('country_name', profile['country']),
              'SUPPORT_EMAIL': profile['support_email'], 'ADDRESS_LOCALITY': profile.get('address_locality', '[ADRES BELİRLENECEK]'),
              'SELLER_ROLE': profile.get('seller_role', '[ROL BELİRLENECEK]'),
              'LEGAL_STATUS': profile.get('legal_status', '[HUKUKİ STATÜ BELİRLENECEK]'),
              'SUPPORT_SCOPE': profile.get('support_scope', '[DESTEK KAPSAMI BELİRLENECEK]')}
    for key, value in fields.items():
        text = text.replace('{{' + key + '}}', value)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding='utf-8')
    print('REVIEW_DRAFT=' + str(args.output))
    print('NOT_APPROVED: no binding approval or sale-ready result was created')


if __name__ == '__main__':
    main()
