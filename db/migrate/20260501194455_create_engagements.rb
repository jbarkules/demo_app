class CreateEngagements < ActiveRecord::Migration[8.0]
  def change
    create_table :engagements do |t|
      t.references :subcontractor, null: false, foreign_key: { to_table: :users }
      t.references :counterparty,  null: false, foreign_key: { to_table: :users }
      t.string  :title, null: false
      t.text    :description
      t.date    :started_on
      t.date    :ended_on
      t.integer :status, null: false, default: 0

      t.timestamps
    end

    add_index :engagements, [:subcontractor_id, :counterparty_id]
  end
end
