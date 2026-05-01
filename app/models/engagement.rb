class Engagement < ApplicationRecord
  belongs_to :subcontractor
  belongs_to :counterparty
end
